#!/usr/bin/env python3
import os
import string
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROMPTS_DIR = BASE_DIR / "prompts"

DEFAULT_SEGMENT_URL = "https://sdk.photoroom.com/v1/segment"
DEFAULT_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DOCS_API_REFERENCE_URL = "https://docs.photoroom.com/getting-started/api-reference-openapi"
DOCS_SEGMENT_QUICKSTART_URL = "https://docs.photoroom.com/remove-background-api-basic-plan"
DOCS_DESCRIBE_ANY_CHANGE_URL = "https://docs.photoroom.com/image-editing-api-plus-plan/alpha-describe-any-change"
DOCS_POSITIONING_URL = "https://docs.photoroom.com/image-editing-api-plus-plan/positioning"

DEFAULT_GHOST_MANNEQUIN_PROMPT = (
    "Transform the main clothing item into a realistic ghost mannequin product photo. "
    "Keep natural worn volume and fabric structure, front-facing and clean. "
    "No person or mannequin should be visible. "
    "Show only the main garment with ecommerce-quality sharpness. "
    "Reduce visible wrinkles when possible."
)

DEFAULT_LIFESTYLE_STAGING_PROMPT = (
    "Create a realistic lifestyle product scene featuring the garment in a natural context. "
    "Keep the item as the hero, with clean composition and premium commercial photography quality. "
    "The final image should look like an ecommerce campaign visual, believable and brand-safe."
)

HEIC_EXTENSIONS = {".heic", ".heif"}
HEIC_CONTENT_TYPES = {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}
COMMON_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".tif", ".tiff", ".bmp", ".gif"}

ALLOWED_OUTPUT_VARIANTS = {"ghost_mannequin", "lifestyle_staging"}
ALLOWED_LIGHT_BACKGROUND_COLORS = {"FFFFFF", "F2F4F7", "EAF7EE", "FFEAF4", "EAF2FF"}

PROMPT_FILES = {
    "ghost_mannequin": PROMPTS_DIR / "ghost_mannequin.txt",
    "lifestyle_staging": PROMPTS_DIR / "lifestyle_staging.txt",
}

app = FastAPI(
    title="Photoroom API Playground",
    description="Minimal technical demo for remove background and dual-output apparel workflows.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _as_int(env_var_name: str, fallback: int) -> int:
    value = os.getenv(env_var_name, "").strip()
    if not value:
        return fallback
    try:
        return int(value)
    except ValueError:
        return fallback


def _as_bool(env_var_name: str, fallback: bool) -> bool:
    value = os.getenv(env_var_name, "").strip().lower()
    if not value:
        return fallback
    return value in {"1", "true", "yes", "on"}


def _error_response(status_code: int, code: str, message: str, detail: str | None = None) -> JSONResponse:
    payload: dict[str, str] = {
        "error": code,
        "message": message,
    }
    if detail:
        payload["detail"] = detail
    return JSONResponse(status_code=status_code, content=payload)


def _normalize_hex_color(value: str) -> str | None:
    normalized = value.strip().lstrip("#").upper()
    if len(normalized) != 6:
        return None
    if any(ch not in string.hexdigits for ch in normalized):
        return None
    return normalized


def _load_prompt_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return text


def _prompt_for_variant(variant: str) -> str:
    prompt_path = PROMPT_FILES[variant]
    file_prompt = _load_prompt_text(prompt_path)
    if file_prompt:
        return file_prompt
    if variant == "ghost_mannequin":
        return DEFAULT_GHOST_MANNEQUIN_PROMPT
    return DEFAULT_LIFESTYLE_STAGING_PROMPT


def _is_supported_image_upload(content_type: str, filename: str | None) -> bool:
    if content_type.startswith("image/"):
        return True
    suffix = Path(filename or "").suffix.lower()
    return suffix in HEIC_EXTENSIONS


def _is_heic_upload(content_type: str, filename: str | None) -> bool:
    suffix = Path(filename or "").suffix.lower()
    return content_type in HEIC_CONTENT_TYPES or suffix in HEIC_EXTENSIONS


def _is_supported_non_heic_image_upload(content_type: str, filename: str | None) -> bool:
    if _is_heic_upload(content_type, filename):
        return False
    if content_type.startswith("image/"):
        return True
    suffix = Path(filename or "").suffix.lower()
    return suffix in COMMON_IMAGE_EXTENSIONS


def _effective_upload_media_type(content_type: str, filename: str | None) -> str:
    if content_type.startswith("image/"):
        return content_type
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".avif":
        return "image/avif"
    if suffix in {".tif", ".tiff"}:
        return "image/tiff"
    if suffix == ".bmp":
        return "image/bmp"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".heic":
        return "image/heic"
    if suffix == ".heif":
        return "image/heif"
    return "application/octet-stream"


def _upstream_error_detail(response: requests.Response) -> str:
    raw_text = (response.text or "").strip()
    if not raw_text:
        return ""

    try:
        payload = response.json()
    except ValueError:
        return raw_text[:800]

    if isinstance(payload, dict):
        upstream_message = str(payload.get("message") or payload.get("error") or "").strip()
        upstream_detail = payload.get("detail") or payload.get("details")
        if isinstance(upstream_detail, (dict, list)):
            upstream_detail = str(upstream_detail)
        if upstream_detail:
            detail_text = str(upstream_detail).strip()
            if upstream_message:
                return f"{upstream_message}: {detail_text}"[:800]
            return detail_text[:800]
        if upstream_message:
            return upstream_message[:800]

    return raw_text[:800]


def _validated_api_key() -> tuple[str | None, JSONResponse | None]:
    api_key = os.getenv("PHOTOROOM_API_KEY", "").strip()
    if not api_key:
        return None, _error_response(
            status_code=500,
            code="missing_api_key",
            message="PHOTOROOM_API_KEY is missing in .env.",
        )

    require_sandbox = _as_bool("PHOTOROOM_REQUIRE_SANDBOX", True)
    if require_sandbox and not api_key.startswith("sandbox_"):
        return None, _error_response(
            status_code=400,
            code="sandbox_key_required",
            message="Sandbox mode is required, but PHOTOROOM_API_KEY is not prefixed with sandbox_.",
            detail="Set PHOTOROOM_REQUIRE_SANDBOX=false only if you intentionally want to use a live API key.",
        )

    return api_key, None


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/demo-info")
def demo_info() -> dict[str, object]:
    """Expose demo wiring so the UI (and reviewers) can inspect current runtime config."""
    api_key = os.getenv("PHOTOROOM_API_KEY", "").strip()
    require_sandbox = _as_bool("PHOTOROOM_REQUIRE_SANDBOX", True)

    return {
        "local_endpoint": {"method": "POST", "path": "/api/remove-bg"},
        "advanced_local_endpoint": {"method": "POST", "path": "/api/advanced-edit"},
        "provider_endpoint": {
            "method": "POST",
            "url": os.getenv("PHOTOROOM_SEGMENT_URL", DEFAULT_SEGMENT_URL).strip() or DEFAULT_SEGMENT_URL,
        },
        "advanced_provider_endpoint": {
            "method": "POST",
            "url": os.getenv("PHOTOROOM_EDIT_URL", DEFAULT_EDIT_URL).strip() or DEFAULT_EDIT_URL,
        },
        "provider_docs": {
            "api_reference": DOCS_API_REFERENCE_URL,
            "segment_quickstart": DOCS_SEGMENT_QUICKSTART_URL,
            "describe_any_change": DOCS_DESCRIBE_ANY_CHANGE_URL,
            "positioning": DOCS_POSITIONING_URL,
        },
        "auth_header": "x-api-key",
        "sandbox_mode": {
            "required": require_sandbox,
            "api_key_is_sandbox": api_key.startswith("sandbox_") if api_key else False,
            "note": "Sandbox mode for /v1/segment uses the same endpoint with an API key prefixed by sandbox_.",
        },
        "advanced_variants": {
            "ghost_mannequin": {
                "prompt_file": str(PROMPT_FILES["ghost_mannequin"]),
                "background.color.allowed": sorted(ALLOWED_LIGHT_BACKGROUND_COLORS),
                "referenceBox": os.getenv("PHOTOROOM_ADVANCED_REFERENCE_BOX", "subjectBox").strip() or "subjectBox",
                "outputSize": os.getenv("PHOTOROOM_ADVANCED_OUTPUT_SIZE", "1200x1500").strip() or "1200x1500",
                "horizontalAlignment": os.getenv("PHOTOROOM_ADVANCED_HORIZONTAL_ALIGNMENT", "center").strip() or "center",
                "verticalAlignment": os.getenv("PHOTOROOM_ADVANCED_VERTICAL_ALIGNMENT", "center").strip() or "center",
                "padding": os.getenv("PHOTOROOM_ADVANCED_PADDING", "0.02").strip() or "0.02",
                "margin": os.getenv("PHOTOROOM_ADVANCED_MARGIN", "0.00").strip() or "0.00",
            },
            "lifestyle_staging": {
                "prompt_file": str(PROMPT_FILES["lifestyle_staging"]),
                "outputSize": os.getenv("PHOTOROOM_ADVANCED_STAGING_OUTPUT_SIZE", "1200x1500").strip() or "1200x1500",
            },
        },
        "export.format": os.getenv("PHOTOROOM_ADVANCED_EXPORT_FORMAT", "png").strip() or "png",
        "request_format": "multipart/form-data with image_file",
        "advanced_request_format": (
            "multipart/form-data with image_file + output_variant (ghost_mannequin|lifestyle_staging) + "
            "optional background_color (#RRGGBB, ghost_mannequin only)"
        ),
        "response_format": "binary image",
    }


@app.post("/api/remove-bg")
async def remove_background(image_file: UploadFile = File(...)) -> Response:
    """Proxy remove-background calls to Photoroom /v1/segment with input validation."""
    api_key, error = _validated_api_key()
    if error:
        return error

    content_type = (image_file.content_type or "").lower()
    filename = image_file.filename or ""
    if not _is_supported_image_upload(content_type, filename):
        return _error_response(
            status_code=415,
            code="invalid_file_type",
            message="Only image files are supported (including HEIC/HEIF).",
        )

    file_bytes = await image_file.read()
    if not file_bytes:
        return _error_response(
            status_code=400,
            code="empty_upload",
            message="Uploaded file is empty.",
        )

    max_upload_bytes = _as_int("APP_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES)
    if len(file_bytes) > max_upload_bytes:
        max_size_mb = max_upload_bytes // (1024 * 1024)
        return _error_response(
            status_code=413,
            code="file_too_large",
            message=f"File is too large. Max allowed size is {max_size_mb} MB.",
        )

    segment_url = os.getenv("PHOTOROOM_SEGMENT_URL", DEFAULT_SEGMENT_URL).strip() or DEFAULT_SEGMENT_URL
    timeout_seconds = _as_int("PHOTOROOM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)

    headers = {"x-api-key": api_key}
    files = {
        "image_file": (
            image_file.filename or "upload-image",
            file_bytes,
            _effective_upload_media_type(content_type, filename),
        )
    }

    try:
        upstream_response = requests.post(
            segment_url,
            headers=headers,
            files=files,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return _error_response(
            status_code=502,
            code="network_error",
            message="Could not reach Photoroom API.",
            detail=str(exc),
        )

    if not upstream_response.ok:
        upstream_status = upstream_response.status_code
        detail = _upstream_error_detail(upstream_response)

        if upstream_status in (401, 403):
            message = "Authentication failed with Photoroom API."
        elif upstream_status == 429:
            message = "Photoroom API rate limit reached. Try again shortly."
        elif upstream_status >= 500:
            message = "Photoroom API is temporarily unavailable."
        else:
            message = "Photoroom API rejected the request."

        return _error_response(
            status_code=upstream_status,
            code="photoroom_error",
            message=message,
            detail=detail,
        )

    media_type = upstream_response.headers.get("content-type", "image/png").split(";")[0].strip() or "image/png"
    return Response(
        content=upstream_response.content,
        media_type=media_type,
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/advanced-edit")
async def advanced_edit(
    image_file: UploadFile = File(...),
    output_variant: str = Form("ghost_mannequin"),
    background_color: str = Form(""),
) -> Response:
    """Run one advanced /v2/edit pass for a chosen business variant."""
    api_key, error = _validated_api_key()
    if error:
        return error

    variant = output_variant.strip().lower()
    if variant not in ALLOWED_OUTPUT_VARIANTS:
        return _error_response(
            status_code=400,
            code="invalid_output_variant",
            message="Invalid output_variant. Allowed values: ghost_mannequin, lifestyle_staging.",
        )

    content_type = (image_file.content_type or "").lower()
    filename = image_file.filename or ""
    if _is_heic_upload(content_type, filename):
        return _error_response(
            status_code=415,
            code="unsupported_advanced_format",
            message="HEIC/HEIF is supported in Remove Background mode, but not in Advanced mode (/v2/edit). Please convert to PNG, JPEG or WEBP.",
        )

    if not _is_supported_non_heic_image_upload(content_type, filename):
        return _error_response(
            status_code=415,
            code="invalid_file_type",
            message="Only image files are supported.",
        )

    file_bytes = await image_file.read()
    if not file_bytes:
        return _error_response(
            status_code=400,
            code="empty_upload",
            message="Uploaded file is empty.",
        )

    max_upload_bytes = _as_int("APP_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES)
    if len(file_bytes) > max_upload_bytes:
        max_size_mb = max_upload_bytes // (1024 * 1024)
        return _error_response(
            status_code=413,
            code="file_too_large",
            message=f"File is too large. Max allowed size is {max_size_mb} MB.",
        )

    edit_url = os.getenv("PHOTOROOM_EDIT_URL", DEFAULT_EDIT_URL).strip() or DEFAULT_EDIT_URL
    timeout_seconds = _as_int("PHOTOROOM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)

    headers = {"x-api-key": api_key}
    files = {
        "imageFile": (
            image_file.filename or "upload-image",
            file_bytes,
            _effective_upload_media_type(content_type, filename),
        )
    }

    data = {
        "describeAnyChange.mode": "ai.auto",
        "describeAnyChange.prompt": _prompt_for_variant(variant),
        "export.format": os.getenv("PHOTOROOM_ADVANCED_EXPORT_FORMAT", "png").strip() or "png",
    }

    if variant == "ghost_mannequin":
        requested_background_color = (
            background_color.strip()
            or os.getenv("PHOTOROOM_ADVANCED_BACKGROUND_COLOR", "FFFFFF").strip()
            or "FFFFFF"
        )
        normalized_background_color = _normalize_hex_color(requested_background_color)
        if not normalized_background_color:
            return _error_response(
                status_code=400,
                code="invalid_background_color",
                message="Invalid background color. Use a 6-digit hex color, for example #FFFFFF.",
            )
        if normalized_background_color not in ALLOWED_LIGHT_BACKGROUND_COLORS:
            return _error_response(
                status_code=400,
                code="unsupported_background_color",
                message="Unsupported background color for this demo. Use one of the predefined light swatches.",
            )

        data.update(
            {
                "removeBackground": "true",
                "background.color": normalized_background_color,
                "referenceBox": os.getenv("PHOTOROOM_ADVANCED_REFERENCE_BOX", "subjectBox").strip() or "subjectBox",
                "outputSize": os.getenv("PHOTOROOM_ADVANCED_OUTPUT_SIZE", "1200x1500").strip() or "1200x1500",
                "horizontalAlignment": os.getenv("PHOTOROOM_ADVANCED_HORIZONTAL_ALIGNMENT", "center").strip() or "center",
                "verticalAlignment": os.getenv("PHOTOROOM_ADVANCED_VERTICAL_ALIGNMENT", "center").strip() or "center",
                "padding": os.getenv("PHOTOROOM_ADVANCED_PADDING", "0.02").strip() or "0.02",
                "margin": os.getenv("PHOTOROOM_ADVANCED_MARGIN", "0.00").strip() or "0.00",
                "ignorePaddingAndSnapOnCroppedSides": (
                    os.getenv("PHOTOROOM_ADVANCED_IGNORE_PADDING_SNAP", "false").strip().lower() or "false"
                ),
            }
        )
    else:
        data["removeBackground"] = "false"
        data["outputSize"] = os.getenv("PHOTOROOM_ADVANCED_STAGING_OUTPUT_SIZE", "1200x1500").strip() or "1200x1500"

    try:
        upstream_response = requests.post(
            edit_url,
            headers=headers,
            files=files,
            data=data,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return _error_response(
            status_code=502,
            code="network_error",
            message="Could not reach Photoroom Image Editing API.",
            detail=str(exc),
        )

    if not upstream_response.ok:
        upstream_status = upstream_response.status_code
        detail = _upstream_error_detail(upstream_response)

        if upstream_status in (401, 403):
            message = "Authentication failed with Photoroom API."
        elif upstream_status == 402:
            message = "Photoroom API returned payment required. The /v2/edit endpoint may require a Plus plan."
        elif upstream_status == 429:
            message = "Photoroom API rate limit reached. Try again shortly."
        elif upstream_status >= 500:
            message = "Photoroom API is temporarily unavailable."
        else:
            message = "Photoroom API rejected the advanced edit request."

        return _error_response(
            status_code=upstream_status,
            code="photoroom_error",
            message=message,
            detail=detail,
        )

    media_type = upstream_response.headers.get("content-type", "image/png").split(";")[0].strip() or "image/png"
    return Response(
        content=upstream_response.content,
        media_type=media_type,
        headers={"Cache-Control": "no-store"},
    )

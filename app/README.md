# Photoroom Mini SaaS Demo App

Minimal FastAPI app with two tabs:

1. `Remove background` via Photoroom `POST /v1/segment`
2. `Advanced mode` via Photoroom `POST /v2/edit` with two explicit output variants

## Run

```bash
cd tech
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set PHOTOROOM_API_KEY
uvicorn app.server:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Sandbox mode

- Remove background sandbox uses the same endpoint URL: `https://sdk.photoroom.com/v1/segment`
- Sandbox is controlled by key format (`sandbox_...`)
- This app enforces sandbox keys by default (`PHOTOROOM_REQUIRE_SANDBOX=true`)
- This demo was built and validated with a sandbox key.

## Local API endpoints

- `POST /api/remove-bg`
  - Input: `multipart/form-data` with `image_file`
  - Upstream: `POST https://sdk.photoroom.com/v1/segment`

- `POST /api/advanced-edit`
  - Input: `multipart/form-data` with:
    - `image_file`
    - `output_variant` (`ghost_mannequin` or `lifestyle_staging`)
    - optional `background_color` (`#RRGGBB`) for `ghost_mannequin` only
  - Upstream: `POST https://image-api.photoroom.com/v2/edit`
  - Shared options:
    - `describeAnyChange.mode=ai.auto`
    - `describeAnyChange.prompt` loaded from prompt files
    - `export.format=png` (default)
  - Ghost mannequin options:
    - `background.color` from fixed light swatches
    - `referenceBox=subjectBox`
    - `outputSize=1200x1500`
    - `horizontalAlignment=center`
    - `verticalAlignment=center`
    - `padding` + `margin`
  - Lifestyle staging options:
    - `outputSize=1200x1500`

- `GET /api/demo-info`
  - Returns current endpoint metadata and configuration used by the demo

## Prompt files

- `app/prompts/ghost_mannequin.txt`
- `app/prompts/lifestyle_staging.txt`

These files are the source of truth for `describeAnyChange.prompt`.

## Business rationale (apparel)

- One studio upload creates:
  - one catalog-style ghost mannequin draft
  - one lifestyle marketing draft
- This keeps a simple operational flow while still covering two practical channel needs.

## Upload and format policy

- `APP_MAX_UPLOAD_BYTES` default is `10 MB`
- Remove mode supports HEIC/HEIF
- Advanced mode rejects HEIC/HEIF and expects PNG/JPEG/WEBP-compatible inputs

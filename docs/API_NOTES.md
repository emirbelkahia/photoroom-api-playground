# API Notes - Photoroom

## Endpoints used

- Segmentation: `POST https://sdk.photoroom.com/v1/segment`
- Image editing: `POST https://image-api.photoroom.com/v2/edit`

## Advanced mode contract in this demo

This demo calls `/v2/edit` with two explicit variants:

1. `output_variant=ghost_mannequin`
2. `output_variant=lifestyle_staging`

Shared options:

- `describeAnyChange.mode=ai.auto`
- `describeAnyChange.prompt` from `app/prompts/*.txt`
- `export.format=png`

Ghost mannequin variant options:

- `background.color` from fixed light swatches
- `referenceBox=subjectBox`
- `outputSize=1200x1500`
- `horizontalAlignment=center`
- `verticalAlignment=center`
- `padding`
- `margin`

Lifestyle staging variant options:

- `outputSize=1200x1500`

Format rule:

- HEIC/HEIF is blocked in advanced mode

## Business framing (apparel)

- Ghost mannequin output: fast catalog draft with controlled background.
- Lifestyle staging output: marketing draft in a realistic context.
- One input image produces two channel-oriented assets with one clear workflow.

## Sandbox mode

- Remove background sandbox uses the same segmentation endpoint URL.
- Sandbox is driven by API key format: `sandbox_...`
- Demo enforcement flag: `PHOTOROOM_REQUIRE_SANDBOX=true`
- The demo was built and tested using a sandbox key.

## Auth

Required header:

```text
x-api-key: <PHOTOROOM_API_KEY>
```

## References

- https://www.photoroom.com/api/
- https://docs.photoroom.com/
- https://docs.photoroom.com/image-editing-api-plus-plan/alpha-describe-any-change
- https://docs.photoroom.com/image-editing-api-plus-plan/positioning
- https://sdk.photoroom.com/

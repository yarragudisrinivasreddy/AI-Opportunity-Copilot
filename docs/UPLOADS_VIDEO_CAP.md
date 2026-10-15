# Video upload size (Part 2b decision)

**Chosen: option (a)** — direct upload with a hard cap below Cloud Run’s HTTP/1 request body limit.

| Limit | Value | Source |
|---|---|---|
| Cloud Run request body (HTTP/1) | ~32 MiB | Google Cloud Run docs — verified before relying on it |
| `MAX_VIDEO_BYTES` | **25 MiB** | [`backend/app/core/privacy.py`](../backend/app/core/privacy.py) |
| `MAX_IMAGE_BYTES` | 8 MiB | same |
| `MAX_VIDEO_SECONDS` | 30 | same |
| `MAX_PHOTOS` | 4 | same |

UI copy uses `{p}`, `{pb}`, `{vb}`, `{vs}` filled from `GET /api/config` only (never hard-coded MB in the pack).

Tip shown when uploads are on: record in **720p**, about **15 to {vs} seconds**, so the file stays under **{vb} MB**.

Option (b) (signed GCS upload) deferred — not quick enough before Fri midday.

Part 2b timing test: record which real clip sizes pass under this cap once Vision/DLP verification runs; keep `UPLOADS_ENABLED=false` until then.

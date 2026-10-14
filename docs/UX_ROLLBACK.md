# UX overhaul rollback

**Hard stop:** Fri 16 Oct midday. If `ux-overhaul` is not clearly better and fully verified, do **not** merge or promote; leave live Hosting on the pre-overhaul release.

## Before promoting preview → live

Capture the current live Hosting release ID and version name:

```bash
# with Firebase CLI authenticated (gcloud access token works)
npx firebase-tools hosting:releases:list --project y-srinivasreddy --limit 5
```

Record here before promote:

| Field | Value |
|---|---|
| Captured at (IST) | 2026-10-14 ~23:55 IST |
| Site | `y-srinivasreddy` |
| Live release name / version ID | **FILL BEFORE PROMOTE** (`npx firebase-tools hosting:releases:list --project y-srinivasreddy --limit 5`) |
| Prior git commit on live | `c83fcf4` (pre-overhaul `main` at branch cut) |
| Overhaul branch tip at dry-run | `0fed95a` on `ux-overhaul` |
| Preview channel | `ux-preview` → https://y-srinivasreddy--ux-preview-aspk3ryv.web.app (version `502c642e893a7799`, expires 2026-10-28) |

## Rollback

1. Do not merge `ux-overhaul` to `main`, **or** revert the merge commit.
2. Clone / redeploy Hosting from the recorded release, or redeploy `frontend/dist` built from commit `c83fcf4`.
3. Confirm https://y-srinivasreddy.web.app loads the previous UI and `/api/health` is OK.

## Branch policy

Work stays on `ux-overhaul` until Fri midday gate passes. Delete the branch after merge or after an explicit abandon-cut note in `TASKS.md`.

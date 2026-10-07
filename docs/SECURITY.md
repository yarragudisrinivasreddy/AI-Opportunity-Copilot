# Security

Status of the PRD threat model (section 22). "Verified" means covered by an automated test in this repo.

| # | Threat | Control | Status |
|---|---|---|---|
| T1 | Account takeover / denial-of-wallet | Firebase Auth anonymous tokens; optional App Check (`ENFORCE_APP_CHECK`); per-UID + **global** daily case caps; per-UID + **per-IP** per-minute limits; set a GCP **budget alert** and Vertex quota before submit | PARTIAL: caps live (`GLOBAL_DAILY_CASE_CAP=40`, IP limit 60/min); budget alert `copilot-alert` INR 2000 set; **App Check off**; **Vertex quota cap TODO** |
| T2 | Cross-user access | Ownership check on every case route; foreign and missing ids both 404; Firestore deny-all | Verified (`test_other_users_cannot_see_or_touch_a_case`) |
| T3 | Injection via proposals | Scan + strip, isolated extraction, code scoring, citation validation | Verified on dev attack set; **held-out set needed** |
| T4 | Injection via text in images/docs | Untrusted-data framing; schema-constrained output | TODO: add red-team images |
| T5 | Workplace media leaks faces/PII | Sanitise before storage/model; failures reject; EXIF stripped; originals never stored | Verified with fakes; **Cloud Vision/DLP unverified** |
| T6 | Hallucinated process/brief | Observation vs assumption, evidence refs, human confirmation | Partially verified; brief traceability TODO |
| T7 | Score manipulation | Code scoring | Verified |
| T8 | Secret leakage | Env/Secret Manager; `.gitignore`; no secrets in prompts/logs | Manual: scan the repo before submission |
| T9 | Denial of wallet | Daily case cap, per-minute limiter, size caps, free sample case | Partial: budget alert set; **Vertex quota still open**; limiter is per-instance |
| T10 | Malicious uploads | Magic-byte sniffing, Pillow decode and re-encode, pixel/size caps | Verified |
| T11 | XSS | React escaping; JSON-only API; CSP in `firebase.json` and API | CSP/console clean on Hosting fresh load + live case (2026-10-07); re-check in real Incognito before submit |
| T12 | Retention/deletion | `DELETE /cases/{id}` removes data and media | Verified (in-memory) |
| T13 | Unseen access | Audit log + Cloud Audit Logs | Audit verified |
| T14 | Cross-tenant retrieval | Every query keyed by case id and owner | Verified |

## Rules for contributors
- Never log request bodies, descriptions, filenames or proposal text. Audit `meta` holds counts only.
- Production refuses to start with dev auth, fake LLM, in-memory storage or fake privacy (`config.py`).
- No before-request origin blocking. Headers are set after the response.
- Dev auth (`X-Dev-User`) must never be enabled in a deployed environment.
- Keep API docs disabled in production (done in `main.py`).

# Tasks and status

Dates follow `docs/PRD.md` section 23. Status key: DONE (tested offline), DRAFT (written, unverified live), TODO.

## FR status (PRD section 8)

| FR | Status | Notes |
|---|---|---|
| FR-01 upload image/video/text | DONE | Magic-byte sniffing; 20 MB cap; real phone videos untested. iPhone HEVC `.mov` may fail to decode, which rejects with a clear message |
| FR-02 privacy preprocessing | DONE (logic) / DRAFT (Cloud Vision, DLP) | Local OpenCV Haar detector is DEV ONLY (low recall) |
| FR-03 video frame sampling | DONE | <=1 fps, max 30 frames, audio never read |
| FR-04 Agent 1 schema + evidence rule | DONE (fake) / TODO verify prompts on real images | |
| FR-05 confirmation gate | DONE | |
| FR-06 need-driven questions | DONE | Fixed wording, max 5 |
| FR-07 opportunities (<=3, may be zero) | DONE (fake) / TODO verify | |
| FR-08 deterministic recommendation | DONE | Thresholds are initial values; tune on benchmark |
| FR-09 brief traceability | PARTIAL | Schema and prompt enforce sections and assumptions; **no automated check that each claim traces to the process/answers** (add a validator or an eval) |
| FR-10 ROI ranges only | DONE | Band values in `core/roi.py` are placeholders: review |
| FR-11 Simulated labels | DONE | API flag + UI badge |
| FR-12/13/14 extraction, scoring, rationale validation | DONE (fake) / TODO verify extractor on Gemini | |
| FR-15 injection defense | DONE (rules + isolation + code scoring) | Dev attack set only; need held-out set |
| FR-16 sample case, zero model cost | DONE | Fixture made with fake LLM |
| FR-17 rate limits and budget | PARTIAL | Per-instance limiter + daily case cap. **Budget alert must be set in the GCP console** |
| FR-18 access control | DONE | Ownership checks at the API; Firestore deny-all |
| FR-19 deletion | DONE | Cases, subcollections, media |
| FR-20 audit log | DONE | No PII in entries |
| FR-21 accessibility | PARTIAL | Semantic markup, labels, focus, reduced motion. **Run an audit** (keyboard, screen reader, contrast, zoom) |
| FR-22 health endpoint | DONE | |

## Plan

### Tue 6 Oct (Day 2): wiring and deploy
- [x] GCP project `y-srinivasreddy`, billing linked, APIs enabled (see `docs/DEPLOYMENT.md`). Budget alert `copilot-alert` INR 2000 set; **Vertex quota cap still TODO**.
- [x] Gemini model: `gemini-2.5-flash` in `us-central1` (verified). `gemini-3.5-flash` 404 on this project.
- [x] `python -m scripts.smoke_vertex` passes. Vertex rejects length constraints → `vertex_response_schema()` loosens schema; Pydantic still validates.
- [x] Cloud Run API live (`opportunity-copilot-api`, us-central1). Gate checks: `/api/health`, `/api/sample`, `/api/config` OK.
- [x] Firebase Hosting + anonymous Auth + frontend `.env.local`; Hosting live; sample + **live text E2E through evaluation** OK. CSP/console clean on fresh load (human Incognito pass still nice).
- [x] `firebase.json` region set to `us-central1`; Firestore database id `copilot` (Native); Cloud Run `FIRESTORE_DATABASE=copilot`.
- [x] Manual live text E2E on Hosting (analyse→evaluate); `e2e_browser.py` against deploy still optional.
- [ ] Confirm Builder Cup repo rules in the portal (size limit, branches, attempts).
- [x] GitHub: https://github.com/yarragudisrinivasreddy/AI-Opportunity-Copilot (`main` pushed). Fresh clone ~0.61MB, no `.env`, `pytest` + `npm run build` OK.
- [x] Uploads kill switch (`UPLOADS_ENABLED`); production ships text-only until Vision/DLP verified. Global case cap + per-IP limit live.

### Wed 7 to Fri 9 Oct: real-model quality
- [x] Live **text-only** flow on real Vertex through evaluation (scores + citations looked sane). Prompt tuning on real output still open.
- [ ] Decide by **Fri 9 Oct**: ship photo upload (then verify Vision+DLP on real frames) **or** keep text-only and align deck/DEMO_SCRIPT (no “faces blurred” claim for the live demo).
- [ ] If uploads ship: verify Cloud Vision face detection and Cloud DLP image redaction on real frames; add a privacy test set (E7).
- [ ] Capture demo media (staged, consenting, no real company data) if uploads ship. Re-run `python -m scripts.build_fixtures` after generating the sample process/brief with Gemini if desired.
- [x] **ADK:** keep plain Python (`CaseService` + agents); no ADK wrap. Describe honestly in deck/PRD.
- [ ] Weight sliders on the evaluation screen (backend already accepts `weights`) — nice-to-have after deploy/privacy.

### Sat 10 to Mon 12 Oct: benchmark data
- [ ] Ground-truth labels for 10 processes (human, before any model run). Format: `docs/EVALUATION.md`.
- [ ] 10 proposal sets, 3 to 5 proposals each, from parameter sheets; 2 to 3 humans rank blind. Hold out 3 sets and 3 processes.
- [ ] Write a **held-out attack set** (ideally by someone who has not seen the detector rules). Keep `attacks_dev.json` for regression only.

### Tue 13 Oct: run benchmarks E1 to E8, record numbers with commit and model ID
### Wed 14 Oct: feature freeze; accessibility pass; README; security checks
### Thu 15 to Fri 16 Oct: deck (official template, PDF under 5 MB), video (2:45 to 2:58), incognito test of every link
### Sat 17 Oct: submit in the morning. Sun 18 Oct: buffer only.

## Open decisions (owner Srinivas unless stated)
- Teammate (**by 11 Oct**), GCP project/billing, video owner, product name/domain check, theme in portal dropdown, daily case cap value, who ranks proposals.

## Ideas parked (do not build before freeze)
Provider-facing view, real onboarding, PDF export, multi-vertical live demo, negotiation.

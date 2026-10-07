# Cursor handoff: read this first

You are continuing a hackathon build. Deadline: **submit Sat 17 Oct 2026**, hard stop Sun 18 Oct 11:59 PM IST. Feature freeze: end of Wed 14 Oct. Master spec: `docs/PRD.md`. Task list: `docs/TASKS.md`.

## State of the repo (what was built offline, and how far to trust it)

| Area | State | Trust |
|---|---|---|
| Deterministic core (rubric, ROI, scorer, ranking, injection scan, text PII, privacy pipeline) | Implemented | **Tested** (offline pytest green, incl. uploads kill switch, global case cap, Vertex schema helper) |
| Four agents + structured-output plumbing | Implemented | Fake LLM in tests; **live text E2E through evaluation** on Vertex (`gemini-2.5-flash` / `us-central1`, 2026-10-07) |
| Case workflow, gating, ownership, audit, rate limits | Implemented | Per-UID + **global** daily case caps; per-UID + **per-IP** per-minute limits (live Cloud Run env confirmed) |
| Frontend (5 screens, sample mode, accessible markup) | Implemented | **Verified** on Hosting; live text case OK. Phone / full a11y audit still open |
| Vertex Gemini client (`app/llm/vertex.py`) | Implemented | **Verified** (smoke + live E2E). `GEMINI_MODEL=gemini-2.5-flash`. API schema: length/`minItems`/etc. **stripped** and `$ref` inlined for Vertex; property names like `title`/`description` kept under `properties`; **Pydantic still validates** the response |
| Firestore / GCS | Implemented | **Verified** writes on live cases. Native DB **`copilot`** (`us-central1`); `FirestoreRepository(..., database=settings.firestore_database)`; Cloud Run `FIRESTORE_DATABASE=copilot`; `firebase.json` `"database": "copilot"`. GCS bucket `y-srinivasreddy-copilot-media` |
| Cloud Vision / Cloud DLP | Written | **UNVERIFIED** on real frames → production `UPLOADS_ENABLED=false` (text-only). Decide by Fri 9 Oct whether uploads ship or deck stays text-only |
| Uploads kill switch | Implemented | API 403 + `/api/config` + frontend hides file input (blur/mask notice only shown when uploads on) |
| Firebase Auth (anonymous) | Configured | Anonymous enabled; App Check **not** enforced yet (`ENFORCE_APP_CHECK=false` until registered) |
| Dockerfile | Verified | Cloud Build succeeded for Cloud Run |
| Cloud Run API | Deployed | **Verified** https://opportunity-copilot-api-redqkgtx4a-uc.a.run.app — use **`/api/health`** (not bare `/healthz`) |
| Firebase Hosting | Deployed | **Verified** https://y-srinivasreddy.web.app — rewrite to Cloud Run; CSP/console clean on fresh load + live case (2026-10-07) |
| GitHub | Pushed | https://github.com/yarragudisrinivasreddy/AI-Opportunity-Copilot (`main` only); fresh-clone ~0.61MB, no `.env`, `pytest` + `npm run build` OK |
| Sample case fixture | Fake LLM | Walkthrough only |
| Budget / Vertex quota | Partial | Billing linked; budget alert `copilot-alert` INR 2000 **emails only**; **Vertex quota cap still TODO** (real brake). Cap UX: sample never counts; 429 points to sample |

## Commands

```bash
cd backend && pytest                                  # must stay green
cd backend && uvicorn app.main:app_factory --factory --port 8080 --reload
cd backend && python -m scripts.build_fixtures        # regenerate sample fixtures (fake LLM)
cd backend && python -m eval.run --suite e6 --llm fake        # smoke only; NOT reportable
cd frontend && npm run dev | npm run build | npm run typecheck
cd backend && python scripts/e2e_browser.py          # browser smoke test; needs playwright, backend and vite running
```

## Architecture in five lines

1. Routes (`api/routes.py`) are thin; rules live in `services/cases.py` and `core/`.
2. Agents depend on the `LLMClient` Protocol (`llm/client.py`), never on an SDK. `FakeLLM` for tests, `VertexGeminiClient` for real.
3. LLMs interpret and explain; **code decides** (rubric recommendation, bid scores, ranking, ROI ranges).
4. All user media is sanitised before storage or any model call; failures reject the media. Live demo: media upload off until Vision/DLP verified.
5. All persistence goes through `Repository` / `MediaStore` Protocols (in-memory for tests, Firestore DB `copilot` / GCS for production).

## Non-negotiables (do not "improve" these away)

- Never hard-code a Gemini model ID. It comes from `GEMINI_MODEL`. Verify current IDs on build day.
- Scores, rankings, recommendations and ROI are computed in code. The LLM never outputs a numeric score.
- Provider proposals, uploaded media text and user free text are **untrusted data**: wrap with `prompts.wrap_untrusted`, scan with `core/injection.py`, never concatenate into instructions.
- Every observation needs an `evidence_ref`; otherwise it is an assumption.
- The brief never claims anything was built. Code sets `status="proposal_only"` and the disclaimer.
- ROI is a range with a stated assumption, or nothing. No single-point ROI, no 0-100 "AI score".
- Providers/proposals are labelled **Simulated** everywhere.
- Fake-LLM numbers never go in the deck, video or `evalRuns`. `eval/run.py` marks them `reportable: false`.
- Security headers stay in the after-response middleware only. Do **not** add a before-request origin check (it blocked an evaluator's requests at a previous event).
- Repo hygiene: single branch; keep the repo small; `.gitignore` is already correct, keep it that way; no GitHub Actions workflow files; never commit `.env`, caches or `node_modules`.

## Deviations from the PRD (decided during the build)

1. **No Google ADK.** Orchestration is plain Python (`CaseService` + agents). Describe honestly in the deck.
2. **Firestore rules are deny-all.** The browser never touches Firestore; Cloud Run uses Admin credentials. DB id is **`copilot`** (not `(default)`, which is Datastore-mode on this project).
3. **Originals are never stored.** Sanitisation happens in memory; only sanitised frames reach storage.
4. **Vision agent fallback:** after one retry, ungrounded "observations" are downgraded to "assumption" instead of failing.
5. **Follow-up questions use fixed wording;** the agent only decides which facts are missing.
6. **Expected outcomes come from code** (`core/roi.py` planning bands), not from the model.
7. **Flagged proposals are scored on their remaining content** and shown with a warning; they are not penalised.
8. When target weeks/budget are not supplied, they are inferred from the proposals and the evaluation carries `*_inferred` flags (shown in the UI).
9. **Health URL:** prefer `/api/health` for uptime and gates (Cloud Run edge can swallow `/healthz`).

## Known gaps (highest value first)

See `docs/TASKS.md`. Top items: **Vertex quota cap**; App Check (`ENFORCE_APP_CHECK`); Vision/DLP on real frames **or** keep text-only and align deck/DEMO_SCRIPT by Fri 9 Oct; held-out benchmark data + rankers by 11–12 Oct; **team lock Sun 11 Oct**; accessibility audit; deck and video.

### Live E2E note (2026-10-07)
Text-only case on Hosting → analyse → confirm → discover → brief → simulated proposals → evaluate. Ranking sane (VisionWorks 87% > Apex 72% injection-flagged > LeanBuild 27%); UI showed “citations verified” and injection strip notice. First brief attempt once failed transiently; retry succeeded.

## How to work

- Small PRs mentally: run `pytest` and `npm run build` before every commit.
- When you change a prompt, a rubric threshold, or a scoring formula, update `docs/AGENT_SPEC.md` or `docs/PRD.md` in the same commit and re-run the benchmark.
- Prefer deleting scope to adding it. The cut order is in `docs/PRD.md` section 23.
- If something in this repo contradicts the PRD and you are unsure, keep the safer behaviour and note it in `docs/TASKS.md`.

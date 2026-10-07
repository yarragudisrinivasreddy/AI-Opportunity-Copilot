# Cursor handoff: read this first

You are continuing a hackathon build. Deadline: **submit Sat 17 Oct 2026**, hard stop Sun 18 Oct 11:59 PM IST. Feature freeze: end of Wed 14 Oct. Master spec: `docs/PRD.md`. Task list: `docs/TASKS.md`.

## State of the repo (what was built offline, and how far to trust it)

| Area | State | Trust |
|---|---|---|
| Deterministic core (rubric, ROI, scorer, ranking, injection scan, text PII, privacy pipeline) | Implemented | **Tested** (offline pytest green, incl. uploads kill switch + Vertex schema helper) |
| Four agents + structured-output plumbing | Implemented | Fake LLM in tests; **VisionProcessAgent smoke OK** on live Vertex (`gemini-2.5-flash` / `us-central1`) after loosening `response_schema` |
| Case workflow, gating, ownership, audit, rate limits | Implemented | Tested through the HTTP API |
| Frontend (5 screens, sample mode, accessible markup) | Implemented | `npm run build` OK; uploads UI respects `/api/config`. **Not tested** with real Firebase auth or on a phone |
| Vertex Gemini client (`app/llm/vertex.py`) | Implemented | **Verified** via `scripts.smoke_vertex` (2026-10-07). Model: set `GEMINI_MODEL=gemini-2.5-flash` (3.5 not available on this project yet). Schema constraints stripped for API, Pydantic still validates |
| Firestore / GCS repos (`app/repo/firestore.py`) | Written | Native DB **`copilot`** created in `us-central1`; GCS bucket `y-srinivasreddy-copilot-media` created. Client accepts `FIRESTORE_DATABASE`. **Live read/write UNVERIFIED** until Cloud Run |
| Cloud Vision face detection, Cloud DLP image redaction | Written | **UNVERIFIED**; keep `UPLOADS_ENABLED=false` in production until verified |
| Uploads kill switch | Implemented | API 403 + `/api/config` + frontend hide file input when disabled |
| Firebase Auth (anonymous) + ID-token verification | Written | **UNVERIFIED** — Firebase CLI login / web app config still needed |
| Dockerfile, firebase.json, firestore.rules | Written | **UNVERIFIED** (Cloud Build on first `gcloud run deploy --source`) |
| Sample case fixture | Generated with the **fake** LLM | Walkthrough only; regenerate with Gemini |
| GCP project `y-srinivasreddy` | Linked | Billing linked; APIs enabled; SA `copilot-api` + IAM for Vertex/Firestore/DLP/GCS |

First hour: run `pytest`, then `python -m scripts.smoke_vertex` with real credentials, and fix whatever drifted. Do not assume anything in the UNVERIFIED rows works.

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
4. All user media is sanitised before storage or any model call; failures reject the media.
5. All persistence goes through `Repository` / `MediaStore` Protocols (in-memory for tests, Firestore/GCS for production).

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

1. **No Google ADK yet.** Orchestration is plain Python (`CaseService` + agents). The PRD mentions ADK for the technical-merit story. Decide by 8 Oct: wrap the existing agents as ADK agents (verify the current ADK API first) or keep plain Python and describe it honestly. Do not rewrite the core to fit ADK.
2. **Firestore rules are deny-all.** The browser never touches Firestore; Cloud Run uses Admin credentials. Simpler and safer than owner rules.
3. **Originals are never stored.** Sanitisation happens in memory; only sanitised frames reach storage. (PRD described a short-TTL temp bucket.)
4. **Vision agent fallback:** after one retry, ungrounded "observations" are downgraded to "assumption" instead of failing.
5. **Follow-up questions use fixed wording;** the agent only decides which facts are missing.
6. **Expected outcomes come from code** (`core/roi.py` planning bands), not from the model. Review the band values; they are placeholders.
7. **Flagged proposals are scored on their remaining content** and shown with a warning; they are not penalised.
8. When target weeks/budget are not supplied, they are inferred from the proposals and the evaluation carries `*_inferred` flags (shown in the UI).

## Known gaps (highest value first)

See `docs/TASKS.md` for the full list with owners and dates. Top items: verify Vertex wiring and prompts on real images; deploy; verify Cloud Vision/DLP; build the held-out benchmark data; add weight sliders; accessibility audit; deck and video.

## How to work

- Small PRs mentally: run `pytest` and `npm run build` before every commit.
- When you change a prompt, a rubric threshold, or a scoring formula, update `docs/AGENT_SPEC.md` or `docs/PRD.md` in the same commit and re-run the benchmark.
- Prefer deleting scope to adding it. The cut order is in `docs/PRD.md` section 23.
- If something in this repo contradicts the PRD and you are unsure, keep the safer behaviour and note it in `docs/TASKS.md`.

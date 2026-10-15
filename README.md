# AI Opportunity Copilot

Show us how work is done. We find where AI could help, write a build-ready brief, and compare builder proposals with an injection-resistant evaluator.

Built for the Google Cloud x Hack2skill **AI Builder Cup 2026**. Theme preference: Future of Work (confirm in the portal).

## What it does

1. **SHOW**: a text description of a manual process (photo/video upload is off in the live demo until Cloud Vision + DLP are verified on real frames; when enabled, faces are blurred and sensitive text is masked before any model sees it).
2. **UNDERSTAND**: Gemini reconstructs the process; every step is labelled *observation* (seen) or *assumption* (inferred). The user confirms or edits, then answers only the questions the system needs.
3. **DISCOVER**: up to three AI opportunities scored on a transparent rubric (enums, not made-up numbers). It can say "not a strong AI candidate" or "use a simple rule-based workflow".
4. **BRIEF**: a structured, build-ready brief with human-in-the-loop points, risks, phases and assumptions. Effort estimates are ranges with stated assumptions.
5. **PROPOSALS (simulated)**: seeded provider proposals are extracted by an LLM into fixed fields; **code** scores and ranks them; the LLM only explains, and its citations are verified.

The product produces an opportunity and a brief. It does not build or claim to have built the solution it recommends.

## Google Cloud services

Gemini on Vertex AI (multimodal, structured output), Cloud Run (FastAPI), Firebase Hosting and Auth, Firestore, Cloud Storage, Cloud Vision (face detection), Sensitive Data Protection / Cloud DLP (image PII), Secret Manager. See `docs/ARCHITECTURE.md`.

## Quick start (no Google account needed)

```bash
# Backend (fake LLM, in-memory storage, local face detector)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env
pytest                                   # 82 tests, fully offline
uvicorn app.main:app_factory --factory --port 8080 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                              # http://localhost:5173, proxies /api to :8080
```

Open the app and click **Try the sample case**, or analyse your own text description.

## Using real Gemini

```bash
export LLM_MODE=vertex GCP_PROJECT=... GCP_LOCATION=... GEMINI_MODEL=...   # verify the model ID first
gcloud auth application-default login
python -m scripts.smoke_vertex           # verifies SDK, model, structured output, image input
```

## Layout

```
backend/app/core/      deterministic logic: rubric, ROI, scoring, injection scan, privacy
backend/app/agents/    four agents (vision/process, opportunity, brief, bid evaluator)
backend/app/llm/       LLM Protocol, Vertex client, offline fake
backend/app/services/  case workflow and gating
backend/app/api/       thin HTTP routes
backend/eval/          benchmark metrics and runner
frontend/src/          React + Vite UI
docs/                  PRD and engineering docs (start with CURSOR_HANDOFF.md)
```

## Live demo

- App: https://y-srinivasreddy.web.app
- Health: https://y-srinivasreddy.web.app/api/health
- Photo/video upload is currently **disabled** (`UPLOADS_ENABLED=false`). Use a text description or the sample case.

## For judges

**What it does.** Paste a short description of a manual workplace process. The app maps the steps (observation vs assumption), asks a few need-driven questions, suggests up to three improvements (including “don’t use AI”), writes a build brief, and compares simulated provider proposals with code-based scoring and injection defenses.

**Sample inputs (no sign-in).** Click **Try the sample case** on the home page. It loads a fixed fixture — no Firebase Auth, no Vertex calls, no spend. You can walk SHOW → UNDERSTAND → DISCOVER → BRIEF → COMPARE offline.

**Own-process (live) path.** Click **Describe your own process**. Anonymous Firebase Auth mints a session. Text-only is the supported demo path (`UPLOADS_ENABLED=false`). Example starter text (manufacturing receiving):

> Every morning trucks arrive with steel wire and bar stock. Security writes the vehicle in a paper register. The store clerk matches the delivery challan to the purchase order by hand. An inspector measures five pieces with a vernier caliper and writes readings on a printed sheet. At the end of the day someone types the sheet into Excel. If a lot fails, the supervisor is phoned and the lot is tagged.

**Limits.** Per user **3** live cases/day; global **150** live cases/day across all users (sized from ~₹/case vs demo budget — see `docs/evidence/cost_per_case.json`). Sample never counts. Per-UID ~30 req/min and per-IP ~60 req/min. When a case cap is hit, the API returns **429** with a plain message and the UI offers **Retry** plus **Try the sample case**.

**Data & grounding.** User text is PII-redacted before the model. Process steps are labelled observation vs assumption; the user must confirm the map. Opportunity scores use fixed rubric enums. Proposal scores are computed in code from extracted facts; the model only explains with verified citations. Prompt-injection segments are stripped by rules before extraction; steering attempts are hard-flagged and ranked below clean bids. Model-only “instruction-like” hints show as an advisory badge without a rank cap.

**Guardrails.** Injection scan + isolation; structured JSON schemas; code ranking; CORS allow-list; CSP without wildcards on Hosting; uploads and concept-picture generation kill-switched off for the demo (`UPLOADS_ENABLED=false`, `VISUALS_ENABLED=false`). Discover-screen illustrations are static WebPs: sample caption “AI-generated example illustration”; live caption “Example illustration (not generated from your process)”.

**Services used.** Firebase Hosting, Firebase Anonymous Auth, Cloud Run (FastAPI), Firestore (`copilot`), Cloud Storage (media bucket; unused while uploads off), Gemini on Vertex AI (`gemini-2.5-flash` at `global`, fallback `gemini-2.5-flash-lite` after 429/503/missing-model; image model `gemini-nano-banana-2.1` at `global` when visuals are on), Cloud Vision and Cloud DLP (wired for privacy; not exercised while uploads are off).

**Latency.** Typical model waits: analyse ~17s, discover ~28s, evaluate ~20–30s (extracts parallelised at most 2-wide). The busy banner states these per-step times. On Vertex 429/503 the API retries with jittered exponential backoff (max 3 tries), then the fallback model, then a plain error with **Retry** and the sample-case link (never a raw 502 body).

## Honest limitations

- Providers and proposals are simulated and labelled as such.
- The sample case was produced with an offline fake model; it is a walkthrough, not a benchmark.
- Benchmark numbers must come from `python -m eval.run ... --llm vertex`; fake-LLM numbers are marked not reportable.
- Live media privacy (Vision face blur + DLP image redaction) is implemented but not yet verified on real frames; do not claim it in the deck until that check passes.

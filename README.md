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

## Honest limitations

- Providers and proposals are simulated and labelled as such.
- The sample case was produced with an offline fake model; it is a walkthrough, not a benchmark.
- Benchmark numbers must come from `python -m eval.run ... --llm vertex`; fake-LLM numbers are marked not reportable.
- Live media privacy (Vision face blur + DLP image redaction) is implemented but not yet verified on real frames; do not claim it in the deck until that check passes.

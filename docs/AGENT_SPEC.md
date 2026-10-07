# Agent specification (as implemented)

All agents call `structured_call(client, system, parts, schema, validator, strict, retries=1)`; outputs are Pydantic models. Prompts live in `app/llm/prompts.py`. Untrusted text is wrapped with `wrap_untrusted` and carries a security preamble.

## Agent 1: VisionProcessAgent (`agents/vision_process.py`)
- **Input:** sanitised JPEG frames (labelled `frame_0..`), optional description (PII-redacted and injection-scanned first).
- **Output:** `Process` (steps with `kind` observation/assumption, `evidence_ref`, `missing_fields`).
- **Validator:** every observation cites an allowed ref (`frame_i` or `description`); unique step ids. One retry with the problems appended. If still invalid: invalid refs are cleared and ungrounded observations become assumptions (`strict=False` path).

## Question selection (`agents/questions.py`)
Deterministic. Asks only for fields in `process.missing_fields` not yet answered; max 5; "I don't know" counts as an answer.

## Agent 2: OpportunityAgent (`agents/opportunity.py`)
- **Input:** confirmed process and answers as JSON.
- **Output:** up to 3 `OpportunityDraft` with **enum** rubric. May return none with `not_ai_explanation`.
- **Code adds:** `id`, `strength`, `recommendation`, `flags` via `core/rubric.recommend` (thresholds `WEAK_MAX=7`, `CANDIDATE_MAX=10`). Evidence refs not in {step ids, answer keys} are dropped.

## Agent 3: BriefAgent (`agents/brief.py`)
- **Input:** selected opportunity, confirmed process, answers, optional target weeks/budget.
- **Output:** `BriefDraft` (12 required sections, exactly 3 phases).
- **Code overrides:** `expected_outcomes` always replaced by `core/roi.estimate_effort` (range plus assumption) or empty; adds `status="proposal_only"` and disclaimer; appends an assumption describing the effort baseline or why none is shown. Requirement ids are `R1..Rn` by order of `proposal_requirements`.

## Agent 4: BidEvaluator (`agents/bid_evaluator.py`)
1. **Scan:** `injection.scan(raw_text)` strips instruction-like segments; remaining text is split into `seg_n` segments.
2. **Extract (LLM, isolated per proposal, temperature 0):** `ExtractedProposalDraft`. Code normalises it: exactly one coverage entry per known requirement (missing = not_covered), unknown ids dropped, citations must reference real segment ids, non-positive or absurd numbers become null. Extractor failure yields an empty extraction (scores 0), never a crash.
3. **Score (code):** `core/scoring` (weights default 0.35/0.20/0.15/0.15/0.15, normalised). Target weeks and budget come from the brief; if absent they are inferred from the proposals and flagged.
4. **Rank (code):** overall desc, then technical fit desc, then cost asc, then id.
5. **Rationale (LLM):** must name the top-ranked proposal; each point's score must match the computed score (tolerance 0.005) and its `field_path` must resolve inside that proposal's extracted data. One retry; then a deterministic template.

## Changing prompts or formulas
Update this file and `docs/PRD.md`, run `pytest`, then re-run the relevant benchmark. Never let a model output flow into scoring except through a schema field.

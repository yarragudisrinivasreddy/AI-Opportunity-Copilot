# Benchmark data

## Status (updated with `benchmark_pack/`)

Draft **inputs** live in [`benchmark_pack/`](benchmark_pack/README.md). They are synthetic and small (10 processes, 10 proposal sets, 15 privacy snippets). Report as a **small internal benchmark** — not a production evaluation.

| Piece | Location | Ready for reportable Vertex run? |
|---|---|---|
| Process texts (E1–E4) | `benchmark_pack/processes.json` (+ `.md`) | **Texts ready**; need filled `ground_truth_form.csv` *before* any model run |
| Ground-truth labels | `benchmark_pack/ground_truth_form.csv` | **Empty** — 1 labeller ~2h |
| Proposal texts (E5) | `benchmark_pack/proposal_sets.json` | **Texts ready**; need blind rankings |
| Blind rankings | `benchmark_pack/ranking_sheet_for_rankers.csv` | **Empty** — 2–3 rankers, 30–45 min each; do **not** show `DO_NOT_SHARE_with_rankers_trait_notes.md` |
| Trait notes (analysis only) | `benchmark_pack/DO_NOT_SHARE_with_rankers_trait_notes.md` | Srinivas only — never to rankers |
| Privacy text snippets (E7 text) | `benchmark_pack/privacy_texts.json` | **Ready** for text-privacy recall (frame E7 still open) |
| Held-out attacks (E6) | `benchmark_pack/attacks_brief_for_teammate.md` | **Brief only** — teammate who has not seen `core/injection.py` must deliver `attacks_held_out.json` |
| Dev attacks | `attacks_dev.json` | Regression only — **never** quote in the deck |
| `bid_sets.json` (E5 runner format) | not built yet | Build from proposal_sets + filled ranking sheet + Brief JSON (see `docs/EVALUATION.md`) |

**Order (do not skip):** (1) labeller fills ground truth, (2) rankers fill ranking sheet blind, (3) teammate delivers held-out attacks, (4) only then run E1–E8 with `--llm vertex`. Fake-LLM / FakeImageClient numbers are never reportable.

## Templates (legacy)

Older empty scaffolds: `processes_gt.template.json`, `bid_parameter_sheets.md`, `attacks_held_out.template.json`. Prefer the pack above.

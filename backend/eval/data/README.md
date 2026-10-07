# Benchmark data (human-authored)

Cursor scaffolds templates only. **Humans must fill** process ground-truth, proposal parameter sheets, and the held-out attack set.

| File | Who writes it | Notes |
|---|---|---|
| `processes_gt.json` | Human (before any model run) | Labels for ~10 processes (E1) |
| `bid_parameter_sheets.md` | Human | Hidden quality levels for proposal generation; **not** shown to rankers |
| `bid_sets.json` | Generated from sheets + human rankings | Format in `docs/EVALUATION.md`; hold out 3 sets |
| `attacks_held_out.json` | Someone who has **not** seen detector rules in `core/injection.py` | Reportable E6 only |
| `attacks_dev.json` | Already present | Regression only — never quote in the deck |

Rankers (2–3 people) must be committed by **11–12 Oct**. Team lock: **Sun 11 Oct**.

Do not commit fake-LLM scores into reportable eval results.

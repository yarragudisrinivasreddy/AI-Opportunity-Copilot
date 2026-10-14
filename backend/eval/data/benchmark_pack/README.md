# Benchmark pack (draft material)

What is here vs what humans must do. Nothing in here is a result.

| File | Used for | Who |
|---|---|---|
| processes.md / processes.json | E1 to E4 text descriptions (10 synthetic processes) | ready |
| ground_truth_form.csv | the right answers, filled BEFORE any model run | 1 person, about 2 hours |
| proposal_sets.json | 10 sets of 4 simulated proposals for E5 | ready |
| ranking_sheet_for_rankers.csv | blind ranking by 2 to 3 people | rankers, 30 to 45 min each |
| DO_NOT_SHARE_with_rankers_trait_notes.md | analysis only | Srinivas |
| privacy_texts.json | E7 text privacy recall, 15 synthetic snippets with spans to remove | ready |
| attacks_brief_for_teammate.md | E6 held-out attacks | a teammate who has not seen detector rules |

Order: (1) labeller fills ground_truth_form.csv, (2) rankers fill the ranking sheet without seeing the model output, (3) teammate delivers attacks, (4) only then Cursor runs E1 to E8 with the real model.
Honesty: these are synthetic and small (10 processes, 10 sets, 15 snippets, 20 attacks). Report them as such: "small internal benchmark", with counts. Do not call them a production evaluation.
Note: P02 (pharma) is meant to test whether the system recommends a human-checked workflow and avoids unsafe automation. P03 and P08 to P10 test whether it says a simple workflow is enough.

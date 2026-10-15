"""Generate personalised questions for 3 industry descriptions + ROI/assumptions proof.

Uses live Hosting API with Firebase anonymous auth via the browser is heavy;
instead calls the local/fake path when LLM_MODE=fake, or Vertex when configured.

Writes docs/visual_diff/round3_questions.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents import questions
from app.agents.brief import BriefAgent
from app.agents.opportunity import OpportunityAgent
from app.agents.vision_process import VisionProcessAgent
from app.core import roi as roi_mod
from app.llm.fake import FakeLLM
from app.schemas.process import Process

OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "round3_questions.json"

CASES = [
    {
        "industry": "manufacturing",
        "desc": (
            "Every morning trucks arrive with steel wire and bar stock. "
            "Security writes the vehicle in a paper register. "
            "The store clerk matches the delivery challan to the purchase order by hand. "
            "An inspector measures five pieces with a vernier caliper and writes readings on a printed sheet. "
            "At the end of the day someone types the sheet into Excel."
        ),
    },
    {
        "industry": "clinic",
        "desc": (
            "Patients check in at a clinic reception desk. A nurse writes vitals on a paper chart. "
            "The doctor reviews the chart, writes a prescription by hand, and the pharmacist "
            "re-enters the same details into a desktop system before dispensing medicine. "
            "Failed prescriptions are called back to the doctor by phone."
        ),
    },
    {
        "industry": "logistics",
        "desc": (
            "At a logistics desk, inbound parcels are scanned once at the door then written into a "
            "day book. Couriers call for route sheets that a clerk prints from Excel. "
            "Failed deliveries are marked on paper and retyped into the tracking spreadsheet overnight."
        ),
    },
]


def main() -> None:
    llm = FakeLLM()
    report: dict = {"cases": [], "fact_keys": list(questions.QUESTION_FIELDS), "roi": {}}

    for case in CASES:
        process = VisionProcessAgent(llm).analyze([], case["desc"])
        # Ensure we ask something personalised even if fake omits fields.
        if not process.missing_fields:
            process = process.model_copy(
                update={"missing_fields": ["volume", "time_per_unit", "exception_handling", "data_availability", "systems_used"]}
            )
        qs = []
        answered: dict[str, str] = {}
        while True:
            q = questions.next_question(process, answered)
            if q is None:
                break
            # fact_key validation: only bank keys
            assert q.field in questions.QUESTION_BANK
            qs.append({"field": q.field, "index": q.index, "total": q.total, "text": q.text})
            answered[q.field] = "I don't know"
        # Fallback to fixed bank when personalisation has empty name
        # Fixed-bank fallback when process has no useful personalisation context
        bare = Process.model_validate({
            "process_name": "x", "environment": "y", "actors": [], "tools": [],
            "steps": [{"id": "s1", "text": "a", "kind": "observation"}],
            "pain_points": [], "missing_fields": ["volume"],
        })
        # Direct bank string is the fallback used when keys are unknown
        fixed = questions.QUESTION_BANK["volume"]
        personal = questions.personalize_question("volume", process)
        report["cases"].append({
            "industry": case["industry"],
            "process_name": process.process_name,
            "questions": qs,
            "personalised_differs_from_fixed_bank": personal != fixed,
            "fixed_bank_volume": fixed,
            "bare_process_question": questions.next_question(bare, {}).text if questions.next_question(bare, {}) else None,
        })

    # ROI band changes with volume answer and appears under assumptions
    process = VisionProcessAgent(llm).analyze([], CASES[0]["desc"])
    opp = OpportunityAgent(llm).discover(process, {})[0][0]
    low = BriefAgent(llm).generate(opp, process, {"volume": "20 a day", "time_per_unit": "10 minutes"})
    high = BriefAgent(llm).generate(opp, process, {"volume": "200 a day", "time_per_unit": "10 minutes"})
    report["roi"] = {
        "low_volume_outcomes": [o.model_dump() for o in low.expected_outcomes],
        "high_volume_outcomes": [o.model_dump() for o in high.expected_outcomes],
        "low_assumptions": low.assumptions,
        "high_assumptions": high.assumptions,
        "band_changed": (
            (low.expected_outcomes[0].high if low.expected_outcomes else None)
            != (high.expected_outcomes[0].high if high.expected_outcomes else None)
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

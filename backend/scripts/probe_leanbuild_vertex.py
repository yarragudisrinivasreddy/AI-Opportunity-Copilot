"""Extract LeanBuild tailored text 5× via Vertex; report hard vs model_detected flags."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.oauth2.credentials import Credentials

from app.agents.bid_evaluator import BidEvaluator
from app.agents.seed_proposals import SEED_ROLES, _tailor_structured, tailor_raw_text
from app.core import injection
from app.llm.vertex import VertexGeminiClient
from app.schemas.brief import Brief
from app.schemas.proposal import Proposal
from scripts.smoke_image import _print_access_token

OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "seed_flag_probe.json"


def main() -> None:
    project = os.environ.get("GCP_PROJECT", "y-srinivasreddy")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    sample = json.loads(
        (Path(__file__).resolve().parents[1] / "app/fixtures/sample_case.json").read_text(
            encoding="utf-8"
        )
    )
    brief = Brief.model_validate(sample["brief"])
    props = json.loads(
        (Path(__file__).resolve().parents[1] / "app/fixtures/proposals.json").read_text(
            encoding="utf-8"
        )
    )
    role = SEED_ROLES["p_leanbuild"]
    structured = _tailor_structured(
        Proposal.model_validate(props["p_leanbuild"]["structured"]), brief, role
    )
    raw = tailor_raw_text(structured, brief, role)
    rule = injection.scan(raw)
    print("rule_scan", rule.detected, rule.reasons)

    token = _print_access_token()
    creds = Credentials(token=token)
    # Patch client construction to pass short-lived user token (ADC unavailable in this shell).
    from google import genai

    llm = VertexGeminiClient.__new__(VertexGeminiClient)
    llm._client = genai.Client(
        vertexai=True, project=project, location=location, credentials=creds
    )
    llm._model = model
    ev = BidEvaluator(llm)
    runs = []
    for i in range(5):
        extracted, flag = ev.extract("p_leanbuild", raw, brief)
        runs.append({
            "n": i + 1,
            "detected": flag.detected,
            "reasons": flag.reasons,
            "model_detected_in_draft": extracted.model_detected_injection,
        })
        print(i + 1, runs[-1])
    hard = sum(1 for r in runs if r["detected"])
    model_n = sum(1 for r in runs if r["model_detected_in_draft"])
    out = {
        "method": "local Vertex extract on tailored overpriced LeanBuild text",
        "rule_scan_detected": rule.detected,
        "rule_reasons": rule.reasons,
        "trigger_note": (
            "Prior live false flag (round3_compare_live_scores) had "
            "injection_flagged:p_leanbuild while rule scan matches nothing on LeanBuild text. "
            "Cause: model_detected_injection OR'd into InjectionFlag.detected. "
            "Fix: hard flag / rank penalty = rule scan only; model_detected stays advisory in reasons."
        ),
        "runs": runs,
        "summary": {
            "n": 5,
            "hard_flagged": hard,
            "model_detected_advisory": model_n,
            "clean_hard_flag_rate": f"{hard}/5",
        },
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

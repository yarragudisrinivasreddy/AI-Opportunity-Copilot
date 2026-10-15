"""Rule-scan Apex seed + attacks_dev recall → docs/visual_diff/apex_rule_scan.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import injection  # noqa: E402
from app.fixtures import loader  # noqa: E402

OUT = ROOT.parent / "docs" / "visual_diff" / "apex_rule_scan.json"


def main() -> int:
    attacks = json.loads((ROOT / "eval/data/attacks_dev.json").read_text(encoding="utf-8"))["attacks"]
    missed = [
        a["id"]
        for a in attacks
        if not injection.scan("We deliver in 8 weeks. " + a["text"]).detected
    ]
    raw = json.loads((ROOT / "app/fixtures/proposals.json").read_text(encoding="utf-8"))
    block = raw.get("p_apexml") or {}
    apex_text = block.get("rawText") or block.get("raw_text") or ""
    if not apex_text and "structured" in block:
        # fall back to R6 steering line used in seed
        rr = (block.get("structured") or {}).get("requirement_responses") or []
        apex_text = " ".join(x.get("response", "") for x in rr if isinstance(x, dict))

    rep = injection.scan(apex_text)
    out = {
        "apex_seed": {
            "proposal_id": "p_apexml",
            "rule_scan_detected": rep.detected,
            "reasons": rep.reasons,
            "hard_flag": rep.detected,
        },
        "attacks_dev_recall": {
            "total": len(attacks),
            "detected": len(attacks) - len(missed),
            "missed": missed,
            "recall": f"{len(attacks) - len(missed)}/{len(attacks)}",
            "note": "Dev attack set written alongside detector — regression check, not held-out evidence.",
        },
        "ui_advisory": {
            "badge_key": "flag_advisory",
            "en": "Possible instruction-like text",
            "hard_flag_when": "injection.scan detected only",
            "rank_cap_when": "hard flag only (model_detected alone does not cap rank)",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if rep.detected and not missed else 1


if __name__ == "__main__":
    raise SystemExit(main())

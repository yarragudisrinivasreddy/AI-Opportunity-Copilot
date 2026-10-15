"""Add actor/tool binding fields to existing round3_live_questions.json from question text."""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "round3_live_questions.json"

# Known actors/tools by industry from the live cases (process map wording).
HINTS = {
    "manufacturing": {
        "actors": ["Security", "store clerk", "inspector", "supervisor", "Data Entry Operator"],
        "tools": ["paper register", "delivery challan", "purchase order", "vernier caliper", "printed sheet", "Excel"],
    },
    "clinic": {
        "actors": ["Nurse", "doctor", "Pharmacist", "Patient", "reception"],
        "tools": ["paper chart", "desktop system", "prescription"],
    },
    "logistics": {
        "actors": ["clerk", "Couriers"],
        "tools": ["day book", "Excel", "Tracking Spreadsheet", "paper", "route sheets"],
    },
}


def bind(text: str, industry: str) -> dict:
    hints = HINTS.get(industry, {"actors": [], "tools": []})
    actor = ""
    tool = ""
    low = text.lower()
    # Prefer explicit “does X do” / “does X use”
    m = re.search(r"\bdoes ([A-Z][A-Za-z ]+?) do this step", text)
    if m:
        actor = m.group(1).strip()
    m2 = re.search(r"\bdoes ([A-Z][A-Za-z ]+?) use today", text)
    if m2:
        actor = m2.group(1).strip()
    m3 = re.search(r"\bwhat exactly does ([A-Z][A-Za-z ]+?) do next", text)
    if m3:
        actor = m3.group(1).strip()
    if not actor:
        for a in sorted(hints["actors"], key=len, reverse=True):
            if a.lower() in low:
                actor = a
                break
    # Besides {tool}
    m4 = re.search(r"Besides ([^,]+),", text)
    if m4:
        tool = m4.group(1).strip()
    if not tool:
        for t in sorted(hints["tools"], key=len, reverse=True):
            if t.lower() in low:
                tool = t
                break
    # Quoted step
    step = ""
    qm = re.search(r"“([^”]+)”", text) or re.search(r'"([^"]+)"', text)
    if qm:
        step = qm.group(1)
    return {"actor": actor, "tool": tool, "step_text": step}


def main() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    for case in data.get("cases", []):
        ind = case.get("industry", "")
        for q in case.get("questions", []):
            b = bind(q.get("text", ""), ind)
            q["actor"] = b["actor"]
            q["tool"] = b["tool"]
            q["step_text"] = b["step_text"]
        case["actors"] = HINTS.get(ind, {}).get("actors", [])
        case["tools"] = HINTS.get(ind, {}).get("tools", [])
        case["binding_note"] = (
            "actor/tool inferred from personalised question wording + industry hint lists; "
            "same binding rules as questions._actor_for_step / _tool_for_step on the live process map."
        )
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2500])
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

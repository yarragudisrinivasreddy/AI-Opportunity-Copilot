"""Print seeded proposal scores after evaluate (fake LLM)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.config import Settings
from app.core.local_privacy import StaticFaceDetector
from app.deps import build_context
from app.llm.fake import FakeLLM
from app.main import create_app
from tests.conftest import ALICE


def main() -> None:
    s = Settings(env="test", daily_case_cap=20, rate_limit_per_minute=1000)
    ctx = build_context(s, llm=FakeLLM(), detector=StaticFaceDetector([]))
    c = TestClient(create_app(s, ctx))
    c.ctx = ctx
    cid = c.post("/api/cases", json={}, headers=ALICE).json()["id"]
    c.put(
        f"/api/cases/{cid}/description",
        json={"text": "Operators check parts by hand on a table."},
        headers=ALICE,
    )
    c.post(f"/api/cases/{cid}/analyze", headers=ALICE)
    proc = c.get(f"/api/cases/{cid}", headers=ALICE).json()["process"]["data"]
    c.post(f"/api/cases/{cid}/process/confirm", json={"process": proc}, headers=ALICE)
    for field, ans in [("volume", "1500"), ("time_per_unit", "2 minutes")]:
        c.post(f"/api/cases/{cid}/answers", json={"field": field, "answer": ans}, headers=ALICE)
    d = c.post(f"/api/cases/{cid}/discover", headers=ALICE).json()
    oid = d["opportunities"][0]["id"]
    c.post(
        f"/api/cases/{cid}/brief",
        json={
            "opportunity_id": oid,
            "target_weeks": 12,
            "budget_low_inr": 800_000,
            "budget_high_inr": 1_200_000,
        },
        headers=ALICE,
    )
    seeded = c.post(f"/api/cases/{cid}/proposals/seed", headers=ALICE).json()
    print("seeded", len(seeded), [p["id"] for p in seeded])
    ev = c.post(f"/api/cases/{cid}/evaluate", json={}, headers=ALICE).json()["data"]
    print("ranking", ev["ranking"])
    print("summary", ev["rationale"]["summary"])
    names = {p.id: p.name for p in c.ctx.cases.s.providers}
    for row in ev["scores"]:
        crit = row["criteria"]
        pid = row["proposal_id"]
        print(
            f"{names.get(pid, pid)} ({pid}): "
            f"overall={round(row['overall'] * 100)}% "
            f"tech={round(crit['technical_fit'] * 100)}% "
            f"exp={round(crit['experience'] * 100)}% "
            f"tl={round(crit['timeline'] * 100)}% "
            f"cost={round(crit['cost'] * 100)}% "
            f"risk={round(crit['risk'] * 100)}%"
        )
    flagged = [e["proposal_id"] for e in ev["extracted"] if e["injection_flag"]["detected"]]
    print("flagged", [names.get(x, x) for x in flagged])


if __name__ == "__main__":
    main()

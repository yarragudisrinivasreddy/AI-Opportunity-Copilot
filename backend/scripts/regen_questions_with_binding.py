"""Regen live questions JSON with actor/tool binding for 3 cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agents import questions
from app.schemas.process import Process

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
API = "https://opportunity-copilot-api-814609847961.us-central1.run.app"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "round3_live_questions.json"

CASES = [
    ("manufacturing", (
        "Every morning trucks arrive with steel wire and bar stock. "
        "Security writes the vehicle in a paper register. "
        "The store clerk matches the delivery challan to the purchase order by hand. "
        "An inspector measures five pieces with a vernier caliper and writes on a printed sheet. "
        "At day end someone types the sheet into Excel. Failed lots are phoned to the supervisor."
    )),
    ("clinic", (
        "Patients check in at a clinic reception desk. A nurse writes vitals on a paper chart. "
        "The doctor reviews the chart and writes a prescription by hand. "
        "The pharmacist re-enters the same details into a desktop system before dispensing. "
        "Failed prescriptions are called back to the doctor by phone the same day."
    )),
    ("logistics", (
        "At a logistics desk, inbound parcels are scanned once at the door then written into a day book. "
        "Couriers call for route sheets that a clerk prints from Excel. "
        "Failed deliveries are marked on paper and retyped into the tracking spreadsheet overnight."
    )),
]


def bearer(page) -> str | None:
    return page.evaluate(
        """() => {
          for (const k of Object.keys(localStorage)) {
            if (k.startsWith('firebase:authUser:')) {
              try {
                const o = JSON.parse(localStorage.getItem(k));
                if (o?.stsTokenManager?.accessToken) return o.stsTokenManager.accessToken;
              } catch (e) {}
            }
          }
          return null;
        }"""
    )


def one(page, industry: str, desc: str) -> dict:
    case_id = {"id": None}

    def on_resp(resp):
        try:
            if "/api/cases/" in resp.url:
                cid = resp.url.split("/api/cases/")[1].split("/")[0].split("?")[0]
                if len(cid) >= 8:
                    case_id["id"] = cid
        except Exception:
            pass

    page.on("response", on_resp)
    page.goto(LIVE, wait_until="networkidle")
    page.get_by_test_id("lang").select_option("en")
    page.get_by_test_id("start-own").click()
    page.get_by_test_id("desc").fill(desc)
    page.get_by_test_id("analyse").click()
    page.get_by_test_id("process-map").wait_for(timeout=180_000)
    page.get_by_test_id("confirm-map").click()
    page.wait_for_timeout(1500)
    token = bearer(page)
    cid = case_id["id"]
    assert cid and token
    state = page.evaluate(
        """async ({ api, caseId, token }) => {
          const r = await fetch(api + '/api/cases/' + caseId, {
            headers: { Authorization: 'Bearer ' + token },
          });
          return await r.json();
        }""",
        {"api": API, "caseId": cid, "token": token},
    )
    process = Process.model_validate(state["process"]["data"])
    answered: dict[str, str] = {}
    qs = []
    while True:
        q = questions.next_question(process, answered)
        if q is None:
            break
        # Reconstruct binding from the field's personalised step context
        binding = {"field": q.field, "actor": "", "tool": "", "step_text": ""}
        if q.field == "volume":
            ctx = questions._ctx_at(process, 0) or questions._ctx_at(process, min(1, len(process.steps) - 1))
        elif q.field == "time_per_unit":
            ctx = questions._ctx_at(process, 0)
        elif q.field == "exception_handling":
            ctx = questions._fail_ctx(process) or questions._ctx_at(process, 0)
        elif q.field in ("data_availability", "systems_used"):
            ctx = questions._record_ctx(process)
        else:
            ctx = None
        if ctx:
            binding.update({"actor": ctx.actor, "tool": ctx.tool, "step_text": ctx.text})
        qs.append({
            "label": f"Question {q.index} of {q.total}",
            "field": q.field,
            "text": q.text,
            "actor": binding["actor"],
            "tool": binding["tool"],
            "step_text": binding["step_text"],
        })
        answered[q.field] = "About 40 a day"
    return {
        "industry": industry,
        "process_name": process.process_name,
        "actors": list(process.actors),
        "tools": list(process.tools),
        "questions": qs,
    }


def main() -> None:
    out = {"cases": []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for industry, desc in CASES:
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            try:
                row = one(page, industry, desc)
                out["cases"].append(row)
                print("OK", industry, len(row["questions"]), row["process_name"][:50])
            except Exception as e:
                out["cases"].append({"industry": industry, "error": str(e)})
                print("FAIL", industry, e)
            ctx.close()
        browser.close()
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

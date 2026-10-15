"""Drive to brief via browser (auth), then call seed+evaluate via page.fetch and dump scores."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff"

DESC = (
    "Every morning trucks arrive with steel wire and bar stock. "
    "Security writes the vehicle in a paper register. "
    "The store clerk matches the delivery challan to the purchase order by hand. "
    "An inspector measures five pieces with a vernier caliper and writes readings on a printed sheet. "
    "At the end of the day someone types the sheet into Excel. "
    "If a lot fails, the supervisor is phoned and the lot is tagged."
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(LIVE, wait_until="networkidle")
        page.get_by_test_id("lang").select_option("en")
        page.get_by_test_id("start-own").click()
        page.get_by_test_id("desc").fill(DESC)
        page.get_by_test_id("analyse").click()
        page.get_by_test_id("process-map").wait_for(timeout=180_000)
        page.get_by_test_id("confirm-map").click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=answer-input],[data-testid=find-opportunities]')",
            timeout=90_000,
        )
        for ans in ("About 40 a day", "15 minutes", "Supervisor decides", "Excel and paper", "Paper and Excel"):
            if page.get_by_test_id("find-opportunities").count() and page.get_by_test_id("find-opportunities").is_visible():
                break
            if not page.get_by_test_id("answer-input").count():
                break
            page.get_by_test_id("answer-input").fill(ans)
            page.get_by_test_id("answer").click()
            page.wait_for_function(
                "() => !document.querySelector('[data-testid=busy-popup]')",
                timeout=90_000,
            )
        page.get_by_test_id("find-opportunities").click()
        page.get_by_test_id("opp-A").wait_for(timeout=180_000)
        page.get_by_test_id("opp-A").locator("button.btn").first.click()
        page.get_by_test_id("make-brief").click()
        page.get_by_test_id("brief-view").wait_for(timeout=180_000)
        page.get_by_test_id("to-compare").click()
        page.get_by_test_id("proposals").wait_for(timeout=60_000)
        result = {"seed": None, "evaluate": None, "getCase": None}

        def on_response(resp):
            try:
                u = resp.url
                if resp.request.method != "POST" and "/cases/" not in u:
                    return
                if "/proposals/seed" in u:
                    result["seed"] = {"status": resp.status, "body": resp.text()[:4000]}
                elif u.rstrip("/").endswith("/evaluate") or "/evaluate" in u:
                    result["evaluate"] = {"status": resp.status, "body": resp.text()[:12000]}
                elif resp.request.method == "GET" and "/api/cases/" in u and u.count("/") >= 5:
                    # GET /api/cases/{id}
                    if not u.endswith("/question") and "opportunities" not in u:
                        result["getCase"] = {"status": resp.status, "body": resp.text()[:2000]}
            except Exception as exc:  # noqa: BLE001
                result.setdefault("errors", []).append(str(exc)[:200])

        page.on("response", on_response)
        page.get_by_test_id("seed-proposals").click()
        # Wait until evaluate response arrives or 7 minutes
        page.wait_for_timeout(1000)
        for _ in range(84):  # 84 * 5s = 7 min
            if result.get("evaluate") and page.get_by_test_id("evaluation-view").count():
                break
            page.wait_for_timeout(5000)
        page.get_by_test_id("evaluation-view").wait_for(timeout=120_000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "round3_compare_live_1280.png"), full_page=True)
        page.set_viewport_size({"width": 375, "height": 900})
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "round3_compare_live_375.png"), full_page=True)
        # Parse evaluate body if JSON
        out = {"raw": {k: ({"status": v["status"], "bodyPreview": v["body"][:500]} if v else None) for k, v in result.items() if k != "errors"}}
        ev_body = result.get("evaluate")
        if ev_body and ev_body["status"] == 200:
            try:
                data = json.loads(ev_body["body"])
                body = data.get("data", data)
                names = {}
                gc = result.get("getCase")
                if gc and gc["status"] == 200:
                    try:
                        names = {p["id"]: p["name"] for p in json.loads(gc["body"]).get("providers", [])}
                    except Exception:
                        pass
                out["ranking"] = body.get("ranking")
                out["flags"] = body.get("flags")
                out["rationale"] = (body.get("rationale") or {}).get("summary")
                out["scores"] = [
                    {
                        "id": s["proposal_id"],
                        "name": names.get(s["proposal_id"], s["proposal_id"]),
                        "overall_pct": round(float(s["overall"]) * 100),
                        "criteria_pct": {k: round(float(v) * 100) for k, v in s["criteria"].items()},
                    }
                    for s in body.get("scores", [])
                ]
                # UI extract if present
                if page.get_by_test_id("evaluation-view").count():
                    out["ui"] = page.evaluate(
                        """() => ({
                          notice: document.querySelector('[data-testid=injection-notice]')?.textContent?.trim(),
                          flaggedName: document.querySelector('[data-testid=injection-notice]')?.getAttribute('data-flagged-name'),
                          banner: document.querySelector('[data-testid=compare-banner-count]')?.textContent?.trim(),
                          rows: [...document.querySelectorAll('[data-testid=compare-desktop] tbody tr')].map((tr,i)=>({
                            rank:i+1,
                            name: tr.querySelector('[data-testid^=provider-name-]')?.textContent?.trim(),
                            flagged: tr.getAttribute('data-flagged')==='true',
                            cells: [...tr.querySelectorAll('td')].map(td=>td.innerText.replace(/\\s+/g,' ').trim())
                          }))
                        })"""
                    )
            except Exception as exc:
                out["parse_error"] = str(exc)
                out["evaluate_body"] = ev_body["body"][:3000]
        else:
            out["evaluate_full"] = ev_body
            out["seed_full"] = result.get("seed")
            out["page"] = page.inner_text("body")[:2000]
        (OUT / "round3_compare_live_scores.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False)[:5000])
        browser.close()


if __name__ == "__main__":
    main()

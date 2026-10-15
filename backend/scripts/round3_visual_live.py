"""Generate one concept picture on ux-preview (VISUALS_ENABLED) via own-process path."""
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
    "An inspector measures five pieces with a vernier caliper and writes on a printed sheet. "
    "At day end someone types the sheet into Excel. Failed lots are phoned to the supervisor."
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"url": LIVE}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(LIVE, wait_until="networkidle")
        cfg = page.evaluate("async () => (await fetch('/api/config')).json()")
        report["config"] = cfg
        if not cfg.get("visualsEnabled"):
            report["status"] = "off"
            (OUT / "round3_visual_live.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return
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
        for ans in ("About 40 a day", "15 minutes", "Supervisor decides", "Excel sheets", "Paper and Excel"):
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
        page.get_by_test_id("opp-A").scroll_into_view_if_needed()
        btn = page.get_by_test_id("concept-btn")
        report["conceptBtnVisible"] = btn.count() > 0 and btn.first.is_visible()
        if not report["conceptBtnVisible"]:
            report["status"] = "no_button"
            page.screenshot(path=str(OUT / "round3_visual_live.png"), full_page=True)
            (OUT / "round3_visual_live.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return
        btn.first.click()
        page.wait_for_timeout(2000)
        # Wait for ready / off / error
        # Capture the visual API response for diagnostics (Cloud Run SA path).
        visual_api: dict = {}

        def on_resp(resp):
            if "/visual" in resp.url and resp.request.method == "POST":
                try:
                    visual_api["status_code"] = resp.status
                    visual_api["body"] = resp.json() if resp.ok else {"text": resp.text()[:800]}
                except Exception as exc:  # noqa: BLE001
                    visual_api["err"] = str(exc)[:200]

        page.on("response", on_resp)
        page.wait_for_function(
            """() => {
              if (document.querySelector('[data-testid=concept-live] img')) return true;
              const flow = document.querySelector('[data-testid=flow]')?.innerText || '';
              return /switched off|capacity is full|picture limit|discarded|Image model/i.test(flow);
            }""",
            timeout=180_000,
        )
        report["visualApi"] = visual_api
        report["hasConceptLive"] = page.locator("[data-testid=concept-live]").count() > 0
        report["status"] = "ready" if report["hasConceptLive"] else "failed"
        report["snippet"] = page.locator("[data-testid=flow]").inner_text()[:500] if page.get_by_test_id("flow").count() else ""
        page.screenshot(path=str(OUT / "round3_visual_live.png"), full_page=True)
        if report["hasConceptLive"]:
            page.locator("[data-testid=concept-live]").screenshot(path=str(OUT / "round3_visual_concept.png"))
        browser.close()
    (OUT / "round3_visual_live.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

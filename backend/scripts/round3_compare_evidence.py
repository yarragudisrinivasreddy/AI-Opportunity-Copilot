"""Capture Compare paste UI + Simulated badges at 375 and 1280 on live own-process."""
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


def drive_to_compare(page) -> None:
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
            """() => !document.querySelector('[data-testid=busy-popup]') &&
              !!(document.querySelector('[data-testid=find-opportunities],[data-testid=answer-input]'))""",
            timeout=90_000,
        )
    page.get_by_test_id("find-opportunities").click()
    page.get_by_test_id("opp-A").wait_for(timeout=180_000)
    page.get_by_test_id("opp-A").locator("button.btn").first.click()
    page.get_by_test_id("make-brief").click()
    page.get_by_test_id("brief-view").wait_for(timeout=180_000)
    page.get_by_test_id("to-compare").click()
    if page.get_by_test_id("seed-proposals").count() and page.get_by_test_id("seed-proposals").is_visible():
        page.get_by_test_id("seed-proposals").click()
    if page.get_by_test_id("evaluate").count() and page.get_by_test_id("evaluate").is_visible():
        page.get_by_test_id("evaluate").click()
    page.get_by_test_id("evaluation-view").wait_for(timeout=180_000)


def audit(page) -> dict:
    return page.evaluate(
        """() => {
          const paste = !!document.querySelector('[data-testid=paste-proposal]');
          const pasteH = document.querySelector('[data-testid=paste-proposal] h2')?.textContent?.trim() || '';
          const cards = [...document.querySelectorAll('[data-testid^=compare-card-]')].map(el => ({
            id: el.getAttribute('data-testid'),
            text: el.innerText.slice(0, 200),
            hasSimulated: /Simulated/i.test(el.innerText),
          }));
          const rows = [...document.querySelectorAll('[data-testid=compare-desktop] tbody tr')].map(tr => ({
            text: tr.innerText.replace(/\\s+/g, ' ').slice(0, 120),
            hasSimulated: /Simulated/i.test(tr.innerText),
          }));
          const body = document.body.innerText;
          return {
            pastePresent: paste,
            pasteHeading: pasteH,
            cardCount: cards.length,
            cardsWithSimulated: cards.filter(c => c.hasSimulated).length,
            cards,
            rowCount: rows.length,
            rowsWithSimulated: rows.filter(r => r.hasSimulated).length,
            rows,
            hasApex: /Apex/i.test(body),
            hasRedTeamHint: /injection|flagged|steer|Apex/i.test(body),
          };
        }"""
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Drive once at 1280, screenshot table; then resize to 375 for cards.
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        drive_to_compare(page)
        report["1280"] = audit(page)
        page.screenshot(path=str(OUT / "round3_compare_1280.png"), full_page=True)
        page.set_viewport_size({"width": 375, "height": 800})
        page.wait_for_timeout(400)
        report["375"] = audit(page)
        page.screenshot(path=str(OUT / "round3_compare_375.png"), full_page=True)
        # Paste form visible before/with seed
        page.evaluate("() => window.scrollTo(0, 0)")
        if page.get_by_test_id("paste-proposal").count():
            page.get_by_test_id("paste-proposal").screenshot(path=str(OUT / "round3_paste_ui.png"))
        ctx.close()
        browser.close()
    (OUT / "round3_compare_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote", OUT / "round3_compare_audit.json")


if __name__ == "__main__":
    main()

"""Fetch live personalised questions for 3 industry cases (EN) from ux-preview."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
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


def one(page, industry: str, desc: str) -> dict:
    page.goto(LIVE, wait_until="networkidle")
    page.get_by_test_id("lang").select_option("en")
    page.get_by_test_id("start-own").click()
    page.get_by_test_id("desc").fill(desc)
    page.get_by_test_id("analyse").click()
    page.get_by_test_id("process-map").wait_for(timeout=180_000)
    name = page.evaluate(
        "() => document.querySelector('.titleblock strong')?.textContent?.trim() || ''"
    )
    page.get_by_test_id("confirm-map").click()
    page.wait_for_function(
        "() => document.querySelector('[data-testid=answer-input],[data-testid=find-opportunities]')",
        timeout=90_000,
    )
    qs = []
    for _ in range(5):
        if page.get_by_test_id("find-opportunities").count() and page.get_by_test_id("find-opportunities").is_visible():
            break
        if not page.get_by_test_id("answer-input").count():
            break
        label = page.locator("[data-testid=q-of]").inner_text() if page.locator("[data-testid=q-of]").count() else ""
        text = page.locator("#qh").inner_text() if page.locator("#qh").count() else ""
        qs.append({"label": label, "text": text})
        page.get_by_test_id("answer-input").fill("About 40 a day")
        page.get_by_test_id("answer").click()
        page.wait_for_function(
            """() => !document.querySelector('[data-testid=busy-popup]') &&
              !!(document.querySelector('[data-testid=find-opportunities],[data-testid=answer-input]'))""",
            timeout=90_000,
        )
    return {"industry": industry, "process_name": name, "questions": qs}


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
                print("OK", industry, len(row["questions"]), row["process_name"][:60])
            except Exception as e:
                out["cases"].append({"industry": industry, "error": str(e)})
                print("FAIL", industry, e)
                try:
                    page.screenshot(
                        path=str(OUT.parent / f"round3_q_{industry}_error.png"), full_page=True
                    )
                except Exception:
                    pass
            ctx.close()
        browser.close()
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

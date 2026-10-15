"""Capture 3 sequential busy-popup screenshots as real API steps tick (no timer)."""
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
    "At the end of the day someone types the sheet into Excel."
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shots: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.goto(LIVE, wait_until="networkidle")
        page.get_by_test_id("lang").select_option("en")
        page.get_by_test_id("start-own").click()
        page.get_by_test_id("desc").fill(DESC)

        # Snapshot busy list each time data-busy-done advances (driven by frontend after API calls).
        seen: set[str] = set()

        def on_done(done: str) -> None:
            if done in seen:
                return
            seen.add(done)
            path = OUT / f"round3_busy_done_{done}.png"
            page.get_by_test_id("busy-popup").screenshot(path=str(path))
            states = page.evaluate(
                """() => [...document.querySelectorAll('[data-testid^=busy-step-]')].map(el => ({
                  id: el.getAttribute('data-testid'),
                  state: el.getAttribute('data-state'),
                  text: el.textContent.trim().slice(0, 80),
                }))"""
            )
            shots.append({"done": done, "file": path.name, "steps": states})
            print("captured", path.name, states)

        page.expose_binding("_noop", lambda *_: None)
        page.get_by_test_id("analyse").click()
        page.get_by_test_id("busy-popup").wait_for(timeout=15_000)

        # Poll for done=0,1,2,3 as analyze progresses (no artificial timer advances).
        deadline = page.evaluate("() => Date.now() + 180000")
        while page.evaluate("() => Date.now()") < deadline:
            if not page.get_by_test_id("busy-popup").count():
                break
            done = page.get_by_test_id("busy-steps").get_attribute("data-busy-done") or "0"
            on_done(done)
            if done >= "3":
                # keep last frame briefly
                page.wait_for_timeout(200)
                break
            page.wait_for_timeout(150)

        page.get_by_test_id("process-map").wait_for(timeout=180_000)
        browser.close()

    (OUT / "round3_busy_progress.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    print(json.dumps(shots, indent=2))


if __name__ == "__main__":
    main()

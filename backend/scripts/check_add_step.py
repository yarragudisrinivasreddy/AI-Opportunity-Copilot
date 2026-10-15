"""Check the Add a step button at 375, 768 and 1280 before deploy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parents[2] / "docs" / "demo" / "stills"
BASE = "http://127.0.0.1:5173"
WIDTHS = (375, 768, 1280)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for w in WIDTHS:
            context = browser.new_context(viewport={"width": w, "height": 800}, locale="en-US", color_scheme="light")
            page = context.new_page()
            page.goto(BASE, wait_until="networkidle", timeout=60000)
            if page.get_by_test_id("lang").count():
                page.get_by_test_id("lang").select_option("en")
            page.get_by_test_id("try-sample").click()
            page.get_by_test_id("add-step").wait_for(timeout=30000)
            page.get_by_test_id("add-step").scroll_into_view_if_needed()
            info = page.evaluate(
                """() => {
                  const b = document.querySelector('[data-testid=add-step]');
                  const r = b.getBoundingClientRect();
                  const cs = getComputedStyle(b);
                  const doc = document.documentElement;
                  return {
                    text: b.innerText.replace(/\\s+/g, ' ').trim(),
                    w: Math.round(r.width),
                    h: Math.round(r.height),
                    whiteSpace: cs.whiteSpace,
                    minWidth: cs.minWidth,
                    overflowX: doc.scrollWidth > doc.clientWidth + 1,
                    client: doc.clientWidth,
                    scroll: doc.scrollWidth
                  };
                }"""
            )
            shot = OUT / f"viewport_{w}.png"
            page.screenshot(path=str(shot), full_page=False)
            info["width"] = w
            info["shot"] = str(shot)
            info["ok"] = info["whiteSpace"] == "nowrap" and info["h"] <= 52 and not info["overflowX"]
            report.append(info)
            context.close()
        browser.close()
    print(json.dumps(report, indent=2))
    return 0 if all(item["ok"] for item in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())

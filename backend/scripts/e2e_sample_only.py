"""Sample-only e2e against E2E_BASE_URL (skips live Vertex path)."""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:5173")


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.goto(BASE, wait_until="networkidle")
        page.get_by_test_id("try-sample").click()
        page.get_by_test_id("sample-banner").wait_for()
        page.get_by_test_id("process-map").wait_for()
        page.get_by_test_id("confirm-map").click()
        page.get_by_test_id("questions").wait_for()
        for _ in range(3):
            page.get_by_test_id("question").locator("button.btn-quiet").first.click()
            page.wait_for_timeout(200)
        page.get_by_test_id("discover").wait_for()
        page.get_by_test_id("concept-btn").click()
        page.wait_for_timeout(1200)
        assert page.get_by_test_id("concept-example").count() >= 1
        cap = page.locator("[data-testid=concept-example] figcaption").inner_text()
        assert "AI-generated example illustration" in cap or "उदाहरण" in cap or "ఉదాహరణ" in cap
        page.locator("[data-testid^='select-opportunity-']").first.click()
        page.get_by_test_id("brief-view").wait_for()
        page.get_by_test_id("to-compare").click()
        page.get_by_test_id("evaluation-view").wait_for()
        assert page.get_by_test_id("injection-notice").count() >= 1
        print("SAMPLE_E2E_OK", BASE)
        print("console_errors", errs[:5])
        if errs:
            raise SystemExit("console errors: " + "; ".join(errs[:5]))
        b.close()


if __name__ == "__main__":
    main()

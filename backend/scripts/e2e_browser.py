"""Browser smoke test (needs: pip install playwright && playwright install chromium).
Start the backend (uvicorn app.main:app_factory --factory --port 8080) and `npm run dev` in frontend first.
Run from backend/:  python scripts/e2e_browser.py

Uses data-testid hooks. Live path is text-only (uploads may be off).
Optional: E2E_BASE_URL for Hosting preview (sample path + live with real model).

Local fake-LLM tip: if frontend/.env.local has VITE_FIREBASE_*, the UI sends Bearer
tokens while AUTH_MODE=dev expects X-Dev-User — temporarily rename .env.local for that run.
"""
from playwright.sync_api import sync_playwright
import os

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:5173")


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(BASE)

        # --- Sample (no auth, no model) ---
        page.get_by_test_id("start-sample").click()
        page.get_by_test_id("sample-banner").wait_for()
        assert page.get_by_test_id("process-map").is_visible()
        page.get_by_test_id("find-opportunities").click()
        page.get_by_test_id("discover").wait_for()
        page.locator("[data-testid^='select-opportunity-']").first.click()
        page.get_by_test_id("generate-brief").click()
        page.get_by_test_id("brief-view").wait_for()
        assert page.get_by_test_id("brief-disclaimer").is_visible()
        page.get_by_test_id("continue-proposals").click()
        page.get_by_test_id("evaluation-view").wait_for()
        assert page.get_by_test_id("injection-notice").count() >= 1
        assert page.get_by_text("Simulated").count() >= 1
        print("SAMPLE FLOW OK")

        # --- Live text path (fake LLM locally; real model on preview if configured) ---
        page.get_by_test_id("brand-home").click()
        page.get_by_test_id("start-live").click()
        page.get_by_test_id("show").wait_for()
        page.get_by_test_id("process-desc").fill(
            "Operators check parts by eye, compare with a paper checklist, and write the result by hand."
        )
        page.get_by_test_id("analyse").click()
        page.get_by_test_id("process-map").wait_for(timeout=120_000)
        page.get_by_test_id("confirm-process").click()
        for ans in ["About 1,500 a day", "2 minutes", "Supervisor checks", "Some saved photos"]:
            page.get_by_test_id("answer-input").wait_for(timeout=60_000)
            page.get_by_test_id("answer-input").fill(ans)
            page.get_by_test_id("answer").click()
            page.wait_for_timeout(300)
        page.get_by_test_id("find-opportunities").click()
        page.get_by_test_id("discover").wait_for(timeout=120_000)
        page.locator("[data-testid^='select-opportunity-']").first.click()
        page.get_by_test_id("target-weeks").fill("12")
        page.get_by_test_id("budget-low").fill("800000")
        page.get_by_test_id("budget-high").fill("1200000")
        page.get_by_test_id("generate-brief").click()
        page.get_by_test_id("brief-view").wait_for(timeout=120_000)
        page.get_by_test_id("continue-proposals").click()
        page.get_by_test_id("seed-proposals").click()
        page.get_by_test_id("evaluate").wait_for(timeout=60_000)
        page.get_by_test_id("evaluate").click()
        page.get_by_test_id("evaluation-view").wait_for(timeout=120_000)
        assert page.get_by_test_id("compare-mobile").count() + page.get_by_test_id("compare-desktop").count() >= 1
        page.get_by_test_id("delete-case").click()
        page.get_by_test_id("home").wait_for()
        print("LIVE TEXT FLOW OK")

        assert page.get_by_test_id("footer").inner_text().find("AI-generated") >= 0
        if errors:
            raise SystemExit("console errors: " + "; ".join(errors[:5]))
        print("E2E OK", BASE)
        b.close()


if __name__ == "__main__":
    main()

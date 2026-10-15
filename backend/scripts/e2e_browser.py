"""Browser smoke test (needs: pip install playwright && playwright install chromium).
Start the backend (uvicorn app.main:app_factory --factory --port 8080) and `npm run dev` in frontend first.
Run from backend/:  python scripts/e2e_browser.py

Uses premium-ui data-testid hooks. Live path is text-only (uploads may be off).
Optional: E2E_BASE_URL for Hosting preview. Optional: E2E_LANG=hi to set language before load.

Local fake-LLM tip: if frontend/.env.local has VITE_FIREBASE_*, the UI sends Bearer
tokens while AUTH_MODE=dev expects X-Dev-User — temporarily rename .env.local for that run.
"""
from playwright.sync_api import sync_playwright
import os

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:5173")
LANG = os.environ.get("E2E_LANG", "en")


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(BASE)

        if LANG != "en":
            page.get_by_test_id("lang").select_option(LANG)

        # --- Sample (no auth, no model) ---
        page.get_by_test_id("try-sample").click()
        page.get_by_test_id("sample-banner").wait_for(state="attached")
        assert page.get_by_test_id("process-map").is_visible()
        page.get_by_test_id("confirm-map").click()
        page.get_by_test_id("questions").wait_for()
        for _ in range(3):
            page.get_by_test_id("question").locator("button.btn-quiet").first.click()
            page.wait_for_timeout(200)
        page.get_by_test_id("discover").wait_for()
        assert page.get_by_test_id("flow").is_visible()
        page.get_by_test_id("concept-btn").click()
        # Visible Write-the-brief control carries select-opportunity-* (not a .sr overlay).
        page.locator("[data-testid^='select-opportunity-']").first.click()
        page.get_by_test_id("brief-view").wait_for()
        assert page.get_by_test_id("disclaimer").is_visible()
        page.get_by_test_id("to-compare").click()
        page.get_by_test_id("evaluation-view").wait_for()
        assert page.get_by_test_id("injection-notice").count() >= 1
        assert page.get_by_text("Simulated").count() >= 1 or page.get_by_text("सिम्युलेटेड").count() >= 1
        print("SAMPLE FLOW OK", LANG)

        # --- Live text path (fake LLM locally; real model on preview if configured) ---
        page.get_by_test_id("brand-home").click()
        page.get_by_test_id("start-own").click()
        page.get_by_test_id("show").wait_for()
        page.get_by_test_id("desc").fill(
            "Operators check parts by eye, compare with a paper checklist, and write the result by hand. "
            "A supervisor reviews failed items at the end of each shift."
        )
        page.get_by_test_id("analyse").click()
        page.get_by_test_id("process-map").wait_for(timeout=120_000)
        page.get_by_test_id("confirm-map").click()
        for ans in ["About 1,500 a day", "2 minutes", "Supervisor checks", "Some saved photos", "Excel and paper"]:
            page.wait_for_function(
                """() => {
                  const find = document.querySelector('[data-testid=find-opportunities]');
                  if (find && find.offsetParent !== null) return true;
                  return !!document.querySelector('[data-testid=answer-input]');
                }""",
                timeout=90_000,
            )
            if page.get_by_test_id("find-opportunities").count() and page.get_by_test_id("find-opportunities").is_visible():
                break
            page.get_by_test_id("answer-input").fill(ans)
            page.get_by_test_id("answer").click()
            page.wait_for_function(
                "() => !document.querySelector('[data-testid=busy-popup]')",
                timeout=90_000,
            )
        page.get_by_test_id("find-opportunities").click()
        page.get_by_test_id("discover").wait_for(timeout=120_000)
        assert page.get_by_test_id("flow").is_visible()
        page.locator("[data-testid^='select-opportunity-']").first.click()
        page.get_by_test_id("brief-options").wait_for(timeout=30_000)
        page.get_by_test_id("target-weeks").fill("12")
        page.get_by_test_id("budget-low").fill("800000")
        page.get_by_test_id("budget-high").fill("1200000")
        page.get_by_test_id("make-brief").click()
        try:
            page.get_by_test_id("busy-popup").wait_for(timeout=5_000)
        except Exception:
            pass
        page.get_by_test_id("brief-view").wait_for(timeout=180_000)
        page.get_by_test_id("to-compare").click()
        if page.get_by_test_id("seed-proposals").count() and page.get_by_test_id("seed-proposals").is_visible():
            page.get_by_test_id("seed-proposals").click()
        # Seed may auto-evaluate; only click Evaluate if still shown.
        page.wait_for_function(
            """() => !!document.querySelector('[data-testid=evaluation-view]') ||
              !!(document.querySelector('[data-testid=evaluate]') &&
                 document.querySelector('[data-testid=evaluate]').offsetParent !== null)""",
            timeout=180_000,
        )
        if page.get_by_test_id("evaluate").count() and page.get_by_test_id("evaluate").is_visible():
            page.get_by_test_id("evaluate").click()
        page.get_by_test_id("evaluation-view").wait_for(timeout=180_000)
        assert page.get_by_test_id("compare-mobile").count() + page.get_by_test_id("compare-desktop").count() >= 1
        page.get_by_test_id("delete-case").click()
        page.get_by_test_id("home").wait_for()
        print("LIVE TEXT FLOW OK", LANG)

        assert "AI-generated" in page.get_by_test_id("footer").inner_text() or "AI" in page.get_by_test_id("footer").inner_text()
        if errors:
            raise SystemExit("console errors: " + "; ".join(errors[:5]))
        print("E2E OK", BASE, LANG)
        b.close()


if __name__ == "__main__":
    main()

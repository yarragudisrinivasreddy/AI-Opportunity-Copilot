"""Full-page stills used as scrolling picture for Brief and Compare."""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "demo" / "capture" / "inserts"
BASE = "https://y-srinivasreddy.web.app"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        await page.goto(BASE, wait_until="networkidle", timeout=60000)
        if await page.get_by_test_id("lang").count():
            await page.get_by_test_id("lang").select_option("en")
        await page.get_by_test_id("try-sample").click()
        await page.get_by_test_id("process-map").wait_for(timeout=30000)
        await page.wait_for_function("() => !document.querySelector('[data-testid=busy-popup]')", timeout=30000)
        await page.get_by_test_id("confirm-map").click()
        await page.get_by_test_id("questions").wait_for()
        for _ in range(3):
            await page.locator(".opt").nth(1).click()
            await page.get_by_test_id("q-next").click()
            await page.wait_for_timeout(250)
        await page.get_by_test_id("discover").wait_for()
        await page.locator("article.opp").first.locator("button.btn").first.click()
        await page.get_by_test_id("brief-view").wait_for()
        await page.evaluate("() => document.querySelectorAll('details').forEach((d) => { d.open = true; })")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / "brief_full.png"), full_page=True)
        await page.get_by_test_id("to-compare").click()
        await page.get_by_test_id("proposals").wait_for()
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / "compare_full.png"), full_page=True)
        await browser.close()
    print("wrote brief_full.png and compare_full.png")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())

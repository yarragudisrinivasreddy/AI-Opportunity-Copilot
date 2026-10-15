"""Capture the home hero only, at 1920 CSS, so the title card is a steady full frame."""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parents[2] / "docs" / "demo" / "capture" / "inserts" / "hero.png"
BASE = "https://y-srinivasreddy.web.app"


async def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
        )
        await page.goto(BASE, wait_until="networkidle", timeout=60000)
        if await page.get_by_test_id("lang").count():
            await page.get_by_test_id("lang").select_option("en")
        await page.evaluate("() => window.scrollTo(0, 0)")
        hero = page.locator("section.hero")
        await hero.wait_for()
        await page.wait_for_timeout(600)
        await hero.screenshot(path=str(OUT))
        box = await hero.bounding_box()
        await browser.close()
    print(OUT, box)


if __name__ == "__main__":
    asyncio.run(main())

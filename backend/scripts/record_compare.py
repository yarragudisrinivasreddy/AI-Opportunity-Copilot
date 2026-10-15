"""Finish Take A: Compare only. Sample clicks are off-camera; the clip starts on Compare."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_take_a import (  # noqa: E402
    BASE,
    INIT,
    INSERTS,
    OUT,
    Screencast,
    eased_scroll,
    move,
    record,
    reveal,
    shot,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-extensions", "--hide-scrollbars"])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
            locale="en-US",
            color_scheme="light",
        )
        page = await context.new_page()
        await page.add_init_script(INIT)
        await page.goto(BASE, wait_until="networkidle", timeout=60000)
        await page.evaluate(INIT)
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
            await page.wait_for_timeout(200)
        await page.get_by_test_id("discover").wait_for()
        await page.locator("article.opp").first.locator("button.btn").first.click()
        await page.get_by_test_id("brief-view").wait_for()
        await page.get_by_test_id("to-compare").click()
        await page.get_by_test_id("proposals").wait_for()
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)

        session = await context.new_cdp_session(page)
        rec = Screencast(session)
        rec.attach()

        async def compare_body(_t0):
            notice = page.get_by_test_id("injection-notice")
            box = await reveal(page, notice, 420)
            await move(page, box["x"] + 120, box["y"] + 28, 1000)
            await shot(page, notice, INSERTS / "flagged_notice.png")
            await page.wait_for_timeout(2200)
            # At 1920 the option cards are hidden. The ranking table carries the Simulated badges.
            await reveal(page, page.get_by_test_id("table"), 300)
            await page.wait_for_timeout(800)
            rect = await page.evaluate(
                """() => {
                  const el = [...document.querySelectorAll('.badge.b-sim')].find((node) => node.getBoundingClientRect().width > 8);
                  if (!el) return null;
                  const r = el.getBoundingClientRect();
                  return { x: r.x, y: r.y, width: r.width, height: r.height };
                }"""
            )
            print("sim rect", rect, flush=True)
            if rect:
                await move(page, rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2, 900)
                pad = 28
                x = max(0, rect["x"] - pad)
                y = max(0, rect["y"] - pad)
                w = min(900, rect["width"] + 220)
                h = min(420, rect["height"] + 160)
                await page.evaluate("() => window.__demo.hide(true)")
                await page.screenshot(
                    path=str(INSERTS / "simulated.png"),
                    clip={"x": x, "y": y, "width": min(1920 - x, w), "height": min(1080 - y, h)},
                )
                await page.evaluate("() => window.__demo.hide(false)")
                print("insert simulated.png", flush=True)
            await page.wait_for_timeout(2400)

        await record(rec, OUT / "compare.mp4", compare_body)
        await context.close()
        await browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

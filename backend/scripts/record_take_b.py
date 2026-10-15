"""Take B: one live analyse on original text. No names, phones, or emails.

Max two attempts. Stops after a second 429 or other failure.
"""
from __future__ import annotations

import asyncio
import json
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
    click_box,
    encode,
    record,
    reveal,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TEXT = (
    "Each morning a workshop receives cartons of packing material. "
    "A clerk writes the count in a notebook. Later the same count is typed into a spreadsheet. "
    "Damaged cartons are reported to the supervisor in person. "
    "At the end of the week the counts are copied by hand into a summary sheet."
)


async def attempt(browser, n: int) -> dict:
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
    await page.get_by_test_id("start-own").click()
    await page.get_by_test_id("desc").wait_for()
    await page.get_by_test_id("desc").fill(TEXT)
    session = await context.new_cdp_session(page)
    rec = Screencast(session)
    rec.attach()

    async def body(_t0):
        btn = page.get_by_test_id("analyse")
        box = await reveal(page, btn, 640)
        await click_box(page, box, 900)
        try:
            await page.wait_for_function(
                """() => document.querySelector('[data-testid=process-map]')
                    || document.querySelector('[data-testid=error-banner]')""",
                timeout=90000,
            )
        except Exception as exc:
            print(f"attempt {n} timed out: {exc}", flush=True)
        await page.wait_for_timeout(2500)

    dest = OUT / "live.mp4"
    meta = await record(rec, dest, body)
    error = None
    if await page.get_by_test_id("error-banner").count():
        error = (await page.get_by_test_id("error-banner").inner_text()).strip()
    mapped = await page.get_by_test_id("process-map").count() > 0
    meta["attempt"] = n
    meta["mapped"] = mapped
    meta["error"] = error
    await context.close()
    return meta


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    INSERTS.mkdir(parents=True, exist_ok=True)
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-extensions", "--hide-scrollbars"])
        for n in (1, 2):
            meta = await attempt(browser, n)
            results.append(meta)
            print(json.dumps(meta, indent=2), flush=True)
            if meta["mapped"]:
                break
            err = (meta.get("error") or "").lower()
            retryable = "429" in err or "limit" in err or "busy" in err or "retry" in err or not meta["mapped"]
            if n == 2 or not retryable:
                break
            print("retrying live run once", flush=True)
            await asyncio.sleep(3)
        await browser.close()
    (OUT / "take_b_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    ok = any(r.get("mapped") for r in results)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

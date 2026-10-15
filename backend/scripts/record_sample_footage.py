"""Record SAMPLE journey MP4 + 1920x1080 screenshots per VIDEO_SCRIPT_AND_SHOTLIST.md.

Uses Playwright video (no cursor jitter). Zoom via device_scale_factor≈1.2 on 1600×900 CSS viewport
→ 1920×1080 buffer. English only. Live URL.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("E2E_BASE_URL", "https://y-srinivasreddy.web.app")
OUT = Path(__file__).resolve().parents[2] / "docs" / "footage"
SCREENS = OUT / "screens"
VID_TMP = OUT / "_pw_video"


def hold(page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def shot(page, name: str) -> None:
    page.screenshot(path=str(SCREENS / name), full_page=False)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    SCREENS.mkdir(parents=True, exist_ok=True)
    if VID_TMP.exists():
        shutil.rmtree(VID_TMP, ignore_errors=True)
    VID_TMP.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1600×900 @ 1.2 scale ≈ 1920×1080; zoom feel ~120%
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            device_scale_factor=1.2,
            record_video_dir=str(VID_TMP),
            record_video_size={"width": 1920, "height": 1080},
            locale="en-US",
            color_scheme="light",
        )
        page = context.new_page()
        # Hide caret / reduce motion for clean footage
        page.add_init_script(
            """() => {
              const s = document.createElement('style');
              s.textContent = '*{caret-color:transparent!important}';
              document.documentElement.appendChild(s);
            }"""
        )

        t0 = time.perf_counter()
        page.goto(BASE, wait_until="networkidle")
        page.get_by_test_id("lang").select_option("en")
        hold(page, 18)  # 0:00–0:18 Home
        shot(page, "01_home.png")

        # Show frame: open own briefly for shot, then home → sample
        page.get_by_test_id("start-own").click()
        page.get_by_test_id("show").wait_for()
        hold(page, 2)
        shot(page, "02_show.png")
        page.get_by_test_id("brand-home").click()
        page.get_by_test_id("home").wait_for()
        hold(page, 1)

        page.get_by_test_id("try-sample").click()
        page.get_by_test_id("process-map").wait_for()
        # pad remaining of 0:18–0:45 (~25s already partly used)
        hold(page, 8)
        shot(page, "03_understand.png")
        hold(page, 12)  # toward 1:15

        page.get_by_test_id("confirm-map").click()
        page.get_by_test_id("questions").wait_for()
        hold(page, 3)
        shot(page, "04_questions.png")
        for _ in range(3):
            page.get_by_test_id("question").locator("button.btn-quiet").first.click()
            hold(page, 2.5)

        page.get_by_test_id("discover").wait_for()
        hold(page, 4)
        # flow view + concept
        page.get_by_test_id("flow").scroll_into_view_if_needed()
        hold(page, 2)
        if page.get_by_test_id("concept-btn").count():
            page.get_by_test_id("concept-btn").click()
            hold(page, 1.5)
        shot(page, "05_discover.png")
        hold(page, 12)

        page.locator("[data-testid^='select-opportunity-']").first.click()
        page.get_by_test_id("brief-view").wait_for()
        hold(page, 8)
        shot(page, "06_brief.png")
        hold(page, 8)

        page.get_by_test_id("to-compare").click()
        page.get_by_test_id("evaluation-view").wait_for()
        hold(page, 12)
        shot(page, "07_compare.png")
        hold(page, 18)  # through ~2:35–2:50

        page.get_by_test_id("brand-home").click()
        page.get_by_test_id("home").wait_for()
        hold(page, 8)

        elapsed = time.perf_counter() - t0
        context.close()
        browser.close()

    vids = list(VID_TMP.glob("*.webm"))
    if not vids:
        print("NO_VIDEO")
        return 1
    dest_webm = OUT / "sample_journey_en_1080p.webm"
    shutil.move(str(vids[0]), str(dest_webm))
    # Prefer mp4 via ffmpeg if available
    dest_mp4 = OUT / "sample_journey_en_1080p.mp4"
    ff = shutil.which("ffmpeg")
    if ff:
        subprocess_ok = os.system(
            f'"{ff}" -y -i "{dest_webm}" -c:v libx264 -pix_fmt yuv420p -movflags +faststart "{dest_mp4}"'
        )
        print("ffmpeg_exit", subprocess_ok)
    else:
        # keep webm; copy name note
        print("ffmpeg_missing; left webm")
    meta = {
        "base": BASE,
        "elapsed_s": round(elapsed, 1),
        "screens": sorted(p.name for p in SCREENS.glob("*.png")),
        "video_webm": str(dest_webm.name),
        "video_mp4": str(dest_mp4.name) if dest_mp4.exists() else None,
        "viewport": "1600x900@1.2 → 1920x1080",
    }
    (OUT / "footage_meta.json").write_text(
        __import__("json").dumps(meta, indent=2), encoding="utf-8"
    )
    print(__import__("json").dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

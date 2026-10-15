"""10-second CDP test clip, then the demo still and architecture crops.

CDP screencast at 1920x1080, encoded CFR 30. Scrollbar hidden. Cursor is in-page.
"""
from __future__ import annotations

import base64
import json
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import asyncio
import math

from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://y-srinivasreddy.web.app"
ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "demo"
STILLS = DEMO / "stills"
CLIP = DEMO / "test_clip"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

INIT = """
(() => {
  const s = document.createElement('style');
  s.textContent = 'html,body{scrollbar-width:none!important}::-webkit-scrollbar{width:0!important;height:0!important;display:none!important}';
  document.documentElement.appendChild(s);
  if (!document.getElementById('rec-cursor')) {
    const c = document.createElement('div');
    c.id = 'rec-cursor';
    c.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><path d="M4 3 L4 24 L10 18 L15 27 L19 25 L14 16 L23 16 Z" fill="#0b1620" stroke="#fff" stroke-width="1.6"/></svg>';
    c.style.cssText = 'position:fixed;z-index:2147483647;left:120px;top:180px;width:28px;height:28px;pointer-events:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,.45));transition:left .12s linear,top .12s linear';
    document.documentElement.appendChild(c);
  }
})();
"""


async def move(page, x: float, y: float) -> None:
    await page.evaluate(
        "(p) => { const c = document.getElementById('rec-cursor'); if (c) { c.style.left = p.x + 'px'; c.style.top = p.y + 'px'; } }",
        {"x": x, "y": y},
    )


async def center(locator) -> tuple[float, float]:
    box = await locator.bounding_box()
    if not box:
        raise RuntimeError("no box")
    return box["x"] + box["width"] / 2, box["y"] + min(box["height"] / 2, 18)


class Screencast:
    def __init__(self, session):
        self.session = session
        self.frames: list[dict] = []

    async def _on(self, params) -> None:
        self.frames.append(params)
        await self.session.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

    def attach(self) -> None:
        self.session.on("Page.screencastFrame", self._on)

    async def start(self) -> None:
        await self.session.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": 85, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1},
        )

    async def stop(self) -> None:
        await self.session.send("Page.stopScreencast")


def encode(frames: list[dict], dest: Path) -> dict:
    raw = dest.parent / "_frames"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    stamps = []
    for i, frame in enumerate(frames):
        data = base64.b64decode(frame["data"])
        (raw / f"f{i:04d}.jpg").write_bytes(data)
        stamps.append(float(frame.get("metadata", {}).get("timestamp") or 0))
    if len(stamps) < 2:
        raise RuntimeError(f"only {len(frames)} screencast frames")
    deltas = [max(stamps[i + 1] - stamps[i], 0.001) for i in range(len(stamps) - 1)]
    listing = raw / "list.txt"
    lines = ["ffconcat version 1.0"]
    for i, delta in enumerate(deltas):
        lines.append(f"file f{i:04d}.jpg")
        lines.append(f"duration {delta:.4f}")
    lines.append(f"file f{len(frames) - 1:04d}.jpg")
    listing.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-fps_mode", "cfr", "-r", "30", "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(dest)],
        check=True, capture_output=True,
    )
    probe = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration",
         "-of", "json", str(dest)],
        check=True, capture_output=True, text=True,
    )
    sheet = dest.with_name("test_clip_frames.png")
    subprocess.run(
        [FFMPEG, "-y", "-i", str(dest), "-vf", "fps=1,scale=384:-1,tile=5x2", "-frames:v", "1", "-update", "1", str(sheet)],
        check=True, capture_output=True,
    )
    return {
        "frames_received": len(frames),
        "source_fps": round((len(frames) - 1) / max(stamps[-1] - stamps[0], 0.001), 2),
        "median_gap_ms": round(statistics.median(deltas) * 1000, 1),
        "max_gap_ms": round(max(deltas) * 1000, 1),
        "probe": json.loads(probe.stdout),
        "sheet": str(sheet),
        "mp4": str(dest),
    }


async def main() -> int:
    STILLS.mkdir(parents=True, exist_ok=True)
    CLIP.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-extensions", "--hide-scrollbars"])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            locale="en-US",
            color_scheme="light",
        )
        page = await context.new_page()
        await page.add_init_script(INIT)
        await page.goto(BASE, wait_until="networkidle", timeout=60000)
        await page.evaluate(INIT)
        if await page.get_by_test_id("lang").count():
            await page.get_by_test_id("lang").select_option("en")
        await page.wait_for_timeout(300)

        session = await context.new_cdp_session(page)
        rec = Screencast(session)
        rec.attach()
        await rec.start()
        btn = page.get_by_test_id("try-sample")
        bx, by = await center(btn)
        clicked = False
        started = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - started < 10:
            t = asyncio.get_event_loop().time() - started
            if not clicked and t >= 3.2:
                await move(page, bx, by)
                await page.wait_for_timeout(180)
                await btn.click()
                clicked = True
            else:
                await move(page, 240 + 1100 * (0.5 + 0.5 * math.sin(t * 1.4)), 160 + 520 * (0.5 + 0.5 * math.cos(t * 1.1)))
            await page.wait_for_timeout(90)
        await rec.stop()
        await page.wait_for_timeout(200)
        await page.get_by_test_id("process-map").wait_for(timeout=30000)
        add_ws = await page.evaluate(
            """() => {
              const b = document.querySelector('[data-testid=add-step]');
              if (!b) return null;
              const r = b.getBoundingClientRect();
              return { whiteSpace: getComputedStyle(b).whiteSpace, h: Math.round(r.height), text: b.innerText.trim() };
            }"""
        )
        report = encode(rec.frames, CLIP / "cursor_10s.mp4")
        report["add_step"] = add_ws

        await page.evaluate(INIT)
        await page.evaluate(
            """() => {
              const step2 = document.querySelectorAll('.route li')[1];
              const asm = document.querySelector('.route li.asm');
              if (!step2 || !asm) return;
              const top = step2.getBoundingClientRect().top + window.scrollY - 24;
              window.scrollTo(0, top);
              const badge = asm.querySelector('.badge');
              const bottom = badge.getBoundingClientRect().bottom;
              if (bottom > window.innerHeight - 16) window.scrollBy(0, bottom - window.innerHeight + 24);
            }"""
        )
        step2_up = page.locator(".route li").nth(1).locator(".icon-btn").first
        x, y = await center(step2_up)
        await move(page, x - 6, y - 4)
        await page.wait_for_timeout(800)
        await step2_up.click()
        await page.wait_for_timeout(400)
        step2_up = page.locator(".route li").nth(1).locator(".icon-btn").first
        x, y = await center(step2_up)
        await move(page, x - 6, y - 4)
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(STILLS / "demo.png"))

        legend = await page.locator(".legend").bounding_box()
        assumption = await page.locator(".route li.asm").first.bounding_box()
        if legend and assumption:
            top = max(0, legend["y"] - 12)
            bottom = min(1080, assumption["y"] + assumption["height"] + 12)
            await page.screenshot(
                path=str(STILLS / "crop_map.png"),
                clip={"x": 80, "y": top, "width": 1760, "height": max(200, bottom - top)},
            )
        else:
            await page.screenshot(path=str(STILLS / "crop_map.png"))

        await page.get_by_test_id("confirm-map").click()
        await page.get_by_test_id("questions").wait_for()
        for _ in range(3):
            await page.locator("[data-testid=question] button.opt").first.click()
            await page.get_by_test_id("q-next").click()
            await page.wait_for_timeout(250)
        await page.get_by_test_id("flow").wait_for(timeout=15000)
        await page.locator(".flow").first.scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        await page.locator(".flow").first.screenshot(path=str(STILLS / "crop_flow.png"))

        await page.locator("[data-testid^='select-opportunity-']").first.click()
        await page.get_by_test_id("brief-view").wait_for()
        await page.get_by_test_id("to-compare").click()
        await page.get_by_test_id("table").wait_for()
        await page.locator("[data-testid=table]").scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        await page.locator("[data-testid=table]").screenshot(path=str(STILLS / "crop_table.png"))
        for name in ("crop_map.png", "crop_flow.png", "crop_table.png"):
            src_img = STILLS / name
            subprocess.run(
                [FFMPEG, "-y", "-i", str(src_img),
                 "-vf", "scale=1180:680:force_original_aspect_ratio=increase,crop=1180:680:0:0",
                 "-update", "1", str(src_img)],
                check=True, capture_output=True,
            )

        plate = (DEMO / "plates" / "architecture.html").read_text(encoding="utf-8")
        plate = (
            plate.replace("CROP_MAP", (STILLS / "crop_map.png").as_uri())
            .replace("CROP_FLOW", (STILLS / "crop_flow.png").as_uri())
            .replace("CROP_TABLE", (STILLS / "crop_table.png").as_uri())
        )
        src = STILLS / "architecture_src.html"
        src.write_text(plate, encoding="utf-8")
        arch = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        ap = await arch.new_page()
        await ap.goto(src.as_uri(), wait_until="networkidle")
        await ap.screenshot(path=str(STILLS / "architecture.png"))
        await arch.close()
        await context.close()
        await browser.close()

    (DEMO / "test_clip_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""20s Understand test: 1920x1080 CSS, device scale 2, eased scroll, curved cursor.

Review file is downscaled to 1920x1080, H.264 CRF 18, CFR 30.
Sharp JPEGs stay in test_clip/understand_sharp for later zoom inserts.
"""
from __future__ import annotations

import asyncio
import base64
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://y-srinivasreddy.web.app"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "demo" / "test_clip"
SHARP = OUT / "understand_sharp"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

INIT = r"""
(() => {
  const style = document.createElement('style');
  style.textContent = `
    html, body { scrollbar-width: none !important; }
    ::-webkit-scrollbar { width: 0 !important; height: 0 !important; display: none !important; }
    #rec-cursor { position: fixed; z-index: 2147483647; width: 28px; height: 28px; pointer-events: none;
      filter: drop-shadow(0 1px 2px rgba(0,0,0,.45)); transform-origin: 4px 3px; }
    #rec-cursor.hot { transform: scale(0.82); }
    #rec-cursor.hot::after { content: ""; position: absolute; left: -6px; top: -6px; width: 26px; height: 26px;
      border: 2px solid #f2a23a; border-radius: 50%; }
  `;
  document.documentElement.appendChild(style);
  if (!document.getElementById('rec-cursor')) {
    const c = document.createElement('div');
    c.id = 'rec-cursor';
    c.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><path d="M4 3 L4 24 L10 18 L15 27 L19 25 L14 16 L23 16 Z" fill="#0b1620" stroke="#fff" stroke-width="1.6"/></svg>';
    c.style.left = '240px';
    c.style.top = '160px';
    document.documentElement.appendChild(c);
  }
  const cursor = () => document.getElementById('rec-cursor');
  const pos = { x: 240, y: 160 };
  const place = (x, y) => {
    pos.x = x; pos.y = y;
    const c = cursor();
    if (c) { c.style.left = (x - 4) + 'px'; c.style.top = (y - 3) + 'px'; }
  };
  const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
  window.__demo = {
    pos: () => ({ ...pos, scroll: window.scrollY }),
    move(x, y, ms) {
      const x0 = pos.x, y0 = pos.y;
      const mx = (x0 + x) / 2, my = (y0 + y) / 2;
      const dx = x - x0, dy = y - y0;
      const len = Math.hypot(dx, dy) || 1;
      const bend = Math.min(160, Math.max(70, len * 0.28));
      const cx = mx + (-dy / len) * bend;
      const cy = my + (dx / len) * bend;
      const t0 = performance.now();
      return new Promise((resolve) => {
        const frame = (now) => {
          const t = Math.min(1, (now - t0) / ms);
          const e = ease(t);
          const u = 1 - e;
          place(u * u * x0 + 2 * u * e * cx + e * e * x, u * u * y0 + 2 * u * e * cy + e * e * y);
          if (t < 1) requestAnimationFrame(frame);
          else resolve();
        };
        requestAnimationFrame(frame);
      });
    },
    hot(on) { cursor()?.classList.toggle('hot', on); },
    scrollBy(dy, ms) {
      const start = window.scrollY;
      const t0 = performance.now();
      return new Promise((resolve) => {
        const frame = (now) => {
          const t = Math.min(1, (now - t0) / ms);
          window.scrollTo(0, start + dy * ease(t));
          if (t < 1) requestAnimationFrame(frame);
          else resolve(window.scrollY);
        };
        requestAnimationFrame(frame);
      });
    },
  };
})();
"""


class Screencast:
    def __init__(self, session):
        self.session = session
        self.frames: list[tuple[float, bytes]] = []

    async def _on(self, params) -> None:
        self.frames.append((time.perf_counter(), base64.b64decode(params["data"])))
        await self.session.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

    def attach(self) -> None:
        self.session.on("Page.screencastFrame", self._on)

    async def start(self) -> None:
        await self.session.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": 80, "maxWidth": 3840, "maxHeight": 2160, "everyNthFrame": 1},
        )

    async def stop(self) -> None:
        try:
            await self.session.send("Page.stopScreencast")
        except Exception:
            pass


def encode(frames: list[tuple[float, bytes]], dest: Path, wall_end: float) -> dict:
    if len(frames) < 8:
        raise RuntimeError(f"only {len(frames)} frames")
    raw = dest.parent / "_u20"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    SHARP.mkdir(parents=True, exist_ok=True)
    stamps = []
    for i, (ts, data) in enumerate(frames):
        (raw / f"f{i:04d}.jpg").write_bytes(data)
        stamps.append(ts)
    # Keep a few sharp frames for zoom inserts (native screencast size).
    for idx in (0, len(frames) // 3, (2 * len(frames)) // 3, len(frames) - 1):
        shutil.copyfile(raw / f"f{idx:04d}.jpg", SHARP / f"f{idx:04d}.jpg")
    gaps = [max(stamps[i + 1] - stamps[i], 0.001) for i in range(len(stamps) - 1)]
    tail = max(0.001, wall_end - stamps[-1])
    lines = ["ffconcat version 1.0"]
    for i, gap in enumerate(gaps):
        lines.append(f"file 'f{i:04d}.jpg'")
        lines.append(f"duration {gap:.4f}")
    lines.append(f"file 'f{len(frames) - 1:04d}.jpg'")
    lines.append(f"duration {tail:.4f}")
    (raw / "list.txt").write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        [
            FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(raw / "list.txt"),
            "-vf", "scale=1920:1080:flags=lanczos",
            "-fps_mode", "cfr", "-r", "30",
            "-c:v", "libx264", "-crf", "18", "-maxrate", "6M", "-bufsize", "12M",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest),
        ],
        check=True,
    )
    probe = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration",
         "-show_entries", "format=size", "-of", "json", str(dest)],
        check=True, capture_output=True, text=True,
    )
    sheet = dest.with_name("understand_20s_frames.png")
    subprocess.run(
        [FFMPEG, "-y", "-i", str(dest), "-vf", "fps=1,scale=384:-1,tile=5x4",
         "-frames:v", "1", "-update", "1", str(sheet)],
        check=True,
    )
    first = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(raw / "f0000.jpg")],
        check=True, capture_output=True, text=True,
    )
    span = stamps[-1] - stamps[0]
    return {
        "frames": len(frames),
        "source_span_s": round(span + tail, 2),
        "median_gap_ms": round(statistics.median(gaps) * 1000, 1),
        "p90_gap_ms": round(sorted(gaps)[int(len(gaps) * 0.9)] * 1000, 1),
        "max_gap_ms": round(max(gaps) * 1000, 1),
        "sharp_size": first.stdout.strip(),
        "probe": json.loads(probe.stdout),
        "mp4": str(dest),
        "sheet": str(sheet),
    }


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
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
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)
        info = await page.evaluate(
            """() => {
              const steps = [...document.querySelectorAll('.route li')];
              const last = steps[steps.length - 1];
              const bottom = last.getBoundingClientRect().bottom + window.scrollY;
              return {
                n: steps.length,
                kinds: steps.map(s => s.className),
                maxScroll: Math.max(0, Math.round(bottom - window.innerHeight + 32)),
              };
            }"""
        )
        session = await context.new_cdp_session(page)
        rec = Screencast(session)
        rec.attach()
        t0 = time.perf_counter()
        await rec.start()

        async def wait_until(second: float) -> None:
            left = second - (time.perf_counter() - t0)
            if left > 0:
                await page.wait_for_timeout(int(left * 1000))

        # Bring step 2 into the upper half with one eased scroll if the banner is covering it.
        box = await page.locator(".route li").nth(1).locator(".icon-btn").first.bounding_box()
        if not box:
            raise RuntimeError("step 2 up button has no box")
        if box["y"] > 780 or box["y"] < 80:
            dy = max(120, min(450, box["y"] - 280))
            ms = int(max(600, min(900, abs(dy) / 0.45)))
            await page.evaluate("(p) => window.__demo.scrollBy(p.dy, p.ms)", {"dy": dy, "ms": ms})
            await page.wait_for_timeout(400)
            box = await page.locator(".route li").nth(1).locator(".icon-btn").first.bounding_box()
        tip_x, tip_y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        await page.evaluate("(p) => window.__demo.move(p.x, p.y, p.ms)", {"x": tip_x, "y": tip_y, "ms": 1100})
        await page.evaluate("() => window.__demo.hot(true)")
        await page.mouse.click(tip_x, tip_y)
        await page.wait_for_timeout(180)
        await page.evaluate("() => window.__demo.hot(false)")
        await wait_until(4.2)

        # Two eased scrolls, 420 px/s, then a hold on the assumptions.
        chunk = min(380, info["maxScroll"])
        await page.evaluate("(p) => window.__demo.scrollBy(p.dy, p.ms)", {"dy": chunk, "ms": 800})
        await wait_until(7.6)
        rest = max(0, info["maxScroll"] - chunk)
        second = min(420, rest) if rest else 320
        await page.evaluate("(p) => window.__demo.scrollBy(p.dy, p.ms)", {"dy": second, "ms": 850})
        await wait_until(11.2)
        # Slow curve across the assumption row, no jump.
        asm = await page.locator(".route li.asm .badge").first.bounding_box()
        if asm:
            await page.evaluate(
                "(p) => window.__demo.move(p.x, p.y, p.ms)",
                {"x": asm["x"] + 28, "y": asm["y"] + 12, "ms": 1000},
            )
        await wait_until(14.6)
        more = max(0, info["maxScroll"] - chunk - second)
        if more > 40:
            await page.evaluate("(p) => window.__demo.scrollBy(p.dy, p.ms)", {"dy": min(400, more), "ms": 800})
        await wait_until(20.0)
        wall_end = time.perf_counter()
        end_state = await page.evaluate("() => window.__demo.pos()")
        await rec.stop()
        await context.close()
        await browser.close()

    report = encode(rec.frames, OUT / "understand_20s.mp4", wall_end)
    report["scroll"] = info
    report["end"] = end_state
    report["scale"] = "css 1920x1080, deviceScaleFactor 2, review downscaled"
    (OUT / "understand_20s_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

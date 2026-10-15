"""Take A: one 1920x1080 CRF-18 clip per sample screen, plus scale-2 inserts.

Viewport is 1920x1080 CSS at device scale 2. Screencast frames stay 1920 and
are expanded to constant 30 fps from wall-clock gaps. Element screenshots
honor device scale 2 and are the zoom-insert sources.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
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
OUT = ROOT / "docs" / "demo" / "capture"
INSERTS = OUT / "inserts"
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
    c.style.left = '280px';
    c.style.top = '220px';
    document.documentElement.appendChild(c);
  }
  const cursor = () => document.getElementById('rec-cursor');
  const pos = { x: 280, y: 220 };
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
    hide(on) {
      const c = cursor();
      if (c) c.style.visibility = on ? 'hidden' : 'visible';
    },
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
        self.on = False

    async def _on(self, params) -> None:
        if self.on:
            self.frames.append((time.perf_counter(), base64.b64decode(params["data"])))
        await self.session.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})

    def attach(self) -> None:
        self.session.on("Page.screencastFrame", self._on)

    async def start(self) -> float:
        self.frames = []
        self.on = True
        await self.session.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": 80, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1},
        )
        return time.perf_counter()

    async def stop(self) -> float:
        wall = time.perf_counter()
        self.on = False
        try:
            await self.session.send("Page.stopScreencast")
        except Exception:
            pass
        return wall


def encode(frames: list[tuple[float, bytes]], dest: Path, wall_end: float) -> dict:
    if len(frames) < 8:
        raise RuntimeError(f"{dest.name}: only {len(frames)} frames")
    raw = dest.parent / f"_{dest.stem}_raw"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    stamps = []
    for i, (ts, data) in enumerate(frames):
        (raw / f"f{i:04d}.jpg").write_bytes(data)
        stamps.append(ts)
    gaps = [max(stamps[i + 1] - stamps[i], 0.001) for i in range(len(stamps) - 1)]
    tail = max(0.001, wall_end - stamps[-1])
    durs = [(f"f{i:04d}.jpg", gap) for i, gap in enumerate(gaps)]
    durs.append((f"f{len(frames) - 1:04d}.jpg", tail))
    seq = raw / "seq"
    seq.mkdir()
    fps = 30
    t = 0.0
    n = 0
    for name, d in durs:
        t_end = t + d
        src = raw / name
        while (n / fps) < t_end - 1e-6:
            dest_frame = seq / f"o{n:04d}.jpg"
            try:
                os.link(src, dest_frame)
            except OSError:
                shutil.copyfile(src, dest_frame)
            n += 1
        t = t_end
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            FFMPEG, "-y", "-framerate", "30", "-i", str(seq / "o%04d.jpg"),
            "-c:v", "libx264", "-crf", "18", "-maxrate", "6M", "-bufsize", "12M",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest),
        ],
        check=True,
    )
    shutil.rmtree(raw, ignore_errors=True)
    probe = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate,nb_frames,duration",
         "-of", "json", str(dest)],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(probe.stdout)["streams"][0]
    print(f"encoded {dest.name} {info.get('duration')}s {info.get('width')}x{info.get('height')} frames={n}", flush=True)
    return {
        "file": str(dest),
        "duration": info.get("duration"),
        "frames_out": n,
        "source_frames": len(frames),
        "median_gap_ms": round(statistics.median(gaps) * 1000, 1),
        "max_gap_ms": round(max(gaps) * 1000, 1),
    }


async def move(page, x, y, ms=1000):
    await page.evaluate("(p) => window.__demo.move(p.x, p.y, p.ms)", {"x": x, "y": y, "ms": ms})


async def click_at(page, x, y):
    await page.evaluate("() => window.__demo.hot(true)")
    await page.mouse.click(x, y)
    await page.wait_for_timeout(180)
    await page.evaluate("() => window.__demo.hot(false)")


async def click_box(page, box, ms=1000):
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await move(page, x, y, ms)
    await click_at(page, x, y)
    return x, y


async def eased_scroll(page, dy: float):
    dy = max(-450, min(450, dy))
    ms = int(max(600, min(900, abs(dy) / 0.42 * 1000)))
    await page.evaluate("(p) => window.__demo.scrollBy(p.dy, p.ms)", {"dy": dy, "ms": ms})
    await page.wait_for_timeout(2400)


async def reveal(page, locator, y=420, attempts=8):
    for _ in range(attempts):
        box = await locator.bounding_box()
        if box and 90 <= box["y"] <= 860:
            return box
        if not box:
            await eased_scroll(page, 360)
            continue
        dy = box["y"] - y
        if abs(dy) < 24:
            return box
        await eased_scroll(page, dy)
    return await locator.bounding_box()


async def shot(page, locator, path: Path):
    """Crop from a viewport screenshot so a hidden or animating node cannot stall the take."""
    path.parent.mkdir(parents=True, exist_ok=True)
    box = await locator.bounding_box()
    if not box or box["height"] < 8 or box["y"] < 20 or box["y"] > 980:
        box = await reveal(page, locator, 420)
    if not box:
        raise RuntimeError(f"no box for {path.name}")
    pad = 18
    x = max(0, box["x"] - pad)
    y = max(0, box["y"] - pad)
    w = min(1920 - x, box["width"] + pad * 2)
    h = min(1080 - y, box["height"] + pad * 2)
    await page.evaluate("() => window.__demo.hide(true)")
    await page.screenshot(path=str(path), clip={"x": x, "y": y, "width": w, "height": h})
    await page.evaluate("() => window.__demo.hide(false)")
    print(f"insert {path.name}", flush=True)


async def shot_pair(page, path: Path):
    """One sharp frame covering an Observation step and an Assumption step."""
    clip = await page.evaluate(
        """() => {
          const vis = (el) => {
            const r = el.getBoundingClientRect();
            return r.height > 20 && r.top > 40 && r.bottom < window.innerHeight - 20;
          };
          const obs = [...document.querySelectorAll('.route li.obs')].find(vis);
          const asm = [...document.querySelectorAll('.route li.asm')].find(vis);
          if (!obs || !asm) return null;
          const a = obs.getBoundingClientRect();
          const b = asm.getBoundingClientRect();
          const top = Math.max(0, Math.min(a.top, b.top) - 12);
          const bottom = Math.min(window.innerHeight, Math.max(a.bottom, b.bottom) + 12);
          const left = Math.max(0, Math.min(a.left, b.left) - 36);
          const right = Math.min(window.innerWidth, Math.max(a.right, b.right) + 16);
          return { x: left, y: top, width: right - left, height: bottom - top };
        }"""
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.evaluate("() => window.__demo.hide(true)")
    if clip and clip["width"] > 80 and clip["height"] > 80:
        await page.screenshot(path=str(path), clip=clip)
    else:
        await page.locator(".legend").screenshot(path=str(path))
    await page.evaluate("() => window.__demo.hide(false)")
    print(f"insert {path.name} clip={bool(clip)}", flush=True)


async def record(rec: Screencast, dest: Path, body):
    print(f"record {dest.name}", flush=True)
    t0 = await rec.start()
    await body(t0)
    wall = await rec.stop()
    await asyncio.sleep(0.15)
    return encode(rec.frames, dest, wall)


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    INSERTS.mkdir(parents=True, exist_ok=True)
    report = {}
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
        await page.evaluate("() => window.__demo.hide(true)")
        await page.screenshot(path=str(INSERTS / "home.png"))
        await page.evaluate("() => window.__demo.hide(false)")

        session = await context.new_cdp_session(page)
        rec = Screencast(session)
        rec.attach()

        async def show_body(_t0):
            await page.wait_for_timeout(800)
            chip = page.get_by_role("button", name="Fill in an example")
            box = await reveal(page, chip, 640)
            await click_box(page, box, 1100)
            await page.wait_for_timeout(2400)
            note = page.get_by_test_id("uploads-off")
            await reveal(page, note, 520)
            await page.wait_for_timeout(2400)

        await page.get_by_test_id("start-own").click()
        await page.get_by_test_id("show").wait_for()
        await page.evaluate("() => window.scrollTo(0, 0)")
        report["show"] = await record(rec, OUT / "show.mp4", show_body)

        await page.get_by_test_id("sample-link").click()
        await page.get_by_test_id("process-map").wait_for(timeout=30000)
        await page.wait_for_function("() => !document.querySelector('[data-testid=busy-popup]')", timeout=30000)
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)

        async def understand_body(_t0):
            up = page.locator(".route li").nth(1).locator(".icon-btn").first
            box = await reveal(page, up, 460)
            await click_box(page, box, 1100)
            await page.wait_for_timeout(2400)
            for _ in range(4):
                both = await page.evaluate(
                    """() => {
                      const vis = (el) => {
                        const r = el.getBoundingClientRect();
                        return r.top > 80 && r.bottom < window.innerHeight - 40;
                      };
                      const obs = [...document.querySelectorAll('.route li.obs')].some(vis);
                      const asms = [...document.querySelectorAll('.route li.asm')].filter(vis);
                      const confirm = document.querySelector('[data-testid=confirm-map]');
                      const cr = confirm ? confirm.getBoundingClientRect() : null;
                      const confirmOn = !!(cr && cr.top > 80 && cr.bottom < window.innerHeight - 16);
                      return { obs, asms: asms.length, confirmOn };
                    }"""
                )
                if both["obs"] and both["asms"] >= 2 and both["confirmOn"]:
                    break
                await eased_scroll(page, 380)
            await shot_pair(page, INSERTS / "observation_assumption.png")
            confirm = page.get_by_test_id("confirm-map")
            box = await confirm.bounding_box()
            if box and 40 < box["y"] < 1000:
                await move(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, 1000)
            await page.wait_for_timeout(2200)

        report["understand"] = await record(rec, OUT / "understand.mp4", understand_body)
        await page.get_by_test_id("confirm-map").click()
        await page.get_by_test_id("questions").wait_for()
        await page.evaluate("() => window.scrollTo(0, 0)")

        async def questions_body(_t0):
            for i in range(3):
                await page.get_by_test_id("question").wait_for()
                opt = page.locator(".opt").nth(1)
                box = await reveal(page, opt, 520)
                await click_box(page, box, 900)
                await page.wait_for_timeout(1600)
                nxt = page.get_by_test_id("q-next")
                box = await reveal(page, nxt, 700)
                await click_box(page, box, 800)
                await page.wait_for_timeout(1800)

        report["questions"] = await record(rec, OUT / "questions.mp4", questions_body)
        await page.get_by_test_id("discover").wait_for(timeout=15000)
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)

        async def discover_body(_t0):
            est = page.locator(".badge.b-est").first
            box = await reveal(page, est, 480)
            await move(page, box["x"] + 20, box["y"] + 12, 1000)
            await shot(page, page.locator("article.opp").first.locator(".facts div").nth(2), INSERTS / "estimate.png")
            await page.wait_for_timeout(2200)
            flow = page.locator(".frow").first
            await reveal(page, flow, 420)
            await page.wait_for_timeout(2200)
            tab = page.get_by_test_id("flow-tab-2")
            box = await reveal(page, tab, 280)
            await click_box(page, box, 900)
            await page.wait_for_timeout(2200)
            verdict = page.locator("article.opp").nth(2).locator(".verdict")
            box = await reveal(page, verdict, 360)
            await move(page, box["x"] + 40, box["y"] + 14, 1000)
            await page.wait_for_timeout(2200)

        report["discover"] = await record(rec, OUT / "discover.mp4", discover_body)
        await page.locator("article.opp").first.locator("button.btn").first.click()
        await page.get_by_test_id("brief-view").wait_for()
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)

        async def brief_body(_t0):
            disc = page.get_by_test_id("disclaimer")
            box = await reveal(page, disc, 280)
            await move(page, box["x"] + 80, box["y"] + 18, 900)
            await shot(page, disc, INSERTS / "proposal_only.png")
            await page.wait_for_timeout(2200)
            opened = await page.evaluate(
                """() => [...document.querySelectorAll('.acc details')].map(d => d.querySelector('summary')?.textContent || '')"""
            )
            print("brief sections", opened, flush=True)
            target = None
            for summary in await page.locator(".acc summary").all():
                text = (await summary.inner_text()).lower()
                if "assum" in text or "stays with people" in text:
                    target = summary
                    if "assum" in text:
                        break
            if target is None:
                target = page.locator(".acc summary").nth(2)
            box = await reveal(page, target, 420)
            await click_box(page, box, 900)
            await page.wait_for_timeout(2400)

        report["brief"] = await record(rec, OUT / "brief.mp4", brief_body)
        await page.get_by_test_id("to-compare").click()
        await page.get_by_test_id("proposals").wait_for()
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)

        async def compare_body(_t0):
            notice = page.get_by_test_id("injection-notice")
            box = await reveal(page, notice, 420)
            await move(page, box["x"] + 120, box["y"] + 28, 1000)
            await shot(page, notice, INSERTS / "flagged_notice.png")
            sim = page.locator(".badge.b-sim").first
            sbox = await sim.bounding_box()
            if sbox and 40 < sbox["y"] < 1000:
                await shot(page, sim, INSERTS / "simulated.png")
            else:
                await reveal(page, sim, 360)
                await shot(page, sim, INSERTS / "simulated.png")
            await page.wait_for_timeout(2200)
            card = page.get_by_test_id("provider-1")
            await reveal(page, card, 300)
            await page.wait_for_timeout(2200)
            table = page.get_by_test_id("table")
            await reveal(page, table, 360)
            await page.wait_for_timeout(2400)

        report["compare"] = await record(rec, OUT / "compare.mp4", compare_body)
        await context.close()
        await browser.close()

    (OUT / "take_a_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

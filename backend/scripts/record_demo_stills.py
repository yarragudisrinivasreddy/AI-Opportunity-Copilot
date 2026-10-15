"""Approval stills for the demo film.

Tries ffmpeg gdigrab of the headed Chromium window. This display is 1680x1050,
so a 1920x1080 window cannot be captured without clipping. If the grabbed frame
is not 1920x1080, fall back to a CDP screenshot at that size.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://y-srinivasreddy.web.app"
ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "demo"
STILLS = DEMO / "stills"
SCREENS = ROOT / "docs" / "footage" / "screens"
PLATE = DEMO / "plates" / "architecture.html"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
TITLE = "CopilotDemoCapture"

CURSOR = """
(() => {
  let c = document.getElementById('rec-cursor');
  if (!c) {
    c = document.createElement('div');
    c.id = 'rec-cursor';
    c.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M4 3 L4 24 L10 18 L15 27 L19 25 L14 16 L23 16 Z" fill="#0b1620" stroke="#fff" stroke-width="1.6"/></svg>';
    c.style.cssText = 'position:fixed;z-index:2147483647;left:80px;top:80px;width:28px;height:28px;pointer-events:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))';
    document.documentElement.appendChild(c);
  }
})();
"""


def find_hwnd(substr: str) -> list[tuple[int, str, tuple[int, int, int, int]]]:
    user32 = ctypes.windll.user32
    found: list[tuple[int, str, tuple[int, int, int, int]]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if not length or not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if substr.lower() in buf.value.lower():
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            found.append((int(hwnd), buf.value, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    user32.EnumWindows(cb, 0)
    return found


def probe_gdigrab(hwnd: int, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "1",
        "-i", f"hwnd={hwnd}", "-frames:v", "1", str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    info = {"returncode": proc.returncode, "stderr_tail": (proc.stderr or "")[-500:]}
    if dest.exists():
        probe = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", str(dest)],
            capture_output=True, text=True,
        )
        info["size"] = (probe.stdout or "").strip()
        info["ok_1920"] = info["size"] == "1920,1080"
    else:
        info["ok_1920"] = False
    return info


def main() -> int:
    STILLS.mkdir(parents=True, exist_ok=True)
    report: dict = {"display": "1680x1050"}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--window-position=0,0",
                "--window-size=1920,1080",
                "--disable-extensions",
                "--force-device-scale-factor=1",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1536, "height": 864},
            device_scale_factor=1.25,
            locale="en-US",
            color_scheme="light",
        )
        page = context.new_page()
        page.add_init_script(CURSOR)
        page.goto(BASE, wait_until="networkidle", timeout=60000)
        page.evaluate(f"() => {{ document.title = '{TITLE}'; }}")
        page.evaluate(CURSOR)
        if page.get_by_test_id("lang").count():
            page.get_by_test_id("lang").select_option("en")
        page.wait_for_timeout(800)

        hwnds = find_hwnd(TITLE)
        report["windows"] = [
            {"hwnd": h, "title": t, "rect": list(r)} for h, t, r in hwnds
        ]
        probe_path = STILLS / "probe_gdigrab.png"
        if hwnds:
            hwnd, title, rect = hwnds[0]
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            report["window_px"] = [w, h]
            report["gdigrab"] = probe_gdigrab(hwnd, probe_path)
        else:
            report["gdigrab"] = {"ok_1920": False, "reason": "window title not found"}

        use_gdigrab = bool(report.get("gdigrab", {}).get("ok_1920"))
        report["method"] = "gdigrab" if use_gdigrab else "cdp"
        if not use_gdigrab:
            report["fallback_reason"] = (
                "gdigrab did not return a 1920x1080 frame. "
                "The desktop is 1680x1050, so a 1920x1080 window is clipped "
                "and the taskbar cannot stay out of a desktop grab."
            )

        page.get_by_test_id("try-sample").click()
        page.get_by_test_id("process-map").wait_for(timeout=20000)
        page.wait_for_timeout(600)
        page.evaluate(CURSOR)
        page.evaluate(
            """() => {
              const el = document.querySelector('.route .badge.b-obs');
              const up = document.querySelector('.route .icon-btn');
              if (!el) return;
              const r = el.getBoundingClientRect();
              const c = document.getElementById('rec-cursor');
              if (c && up) {
                const u = up.getBoundingClientRect();
                c.style.left = (u.x + 4) + 'px';
                c.style.top = (u.y + 6) + 'px';
              }
              const box = document.createElement('div');
              box.style.cssText = `position:fixed;left:${r.x - 8}px;top:${r.y - 6}px;width:${r.width + 16}px;height:${r.height + 12}px;border:3px solid #f2a23a;border-radius:8px;box-shadow:0 0 0 6px rgba(242,162,58,.28);pointer-events:none;z-index:2147483646`;
              document.body.appendChild(box);
            }"""
        )
        page.wait_for_timeout(400)
        demo = STILLS / "demo.png"
        page.screenshot(path=str(demo), type="png")
        report["demo"] = str(demo)

        # Architecture plate at a true 1920x1080 bitmap.
        arch_context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            locale="en-US",
            color_scheme="dark",
        )
        arch_page = arch_context.new_page()
        html = PLATE.read_text(encoding="utf-8")
        html = (
            html.replace("SHOT_UNDERSTAND", (SCREENS / "03_understand.png").as_uri())
            .replace("SHOT_DISCOVER", (SCREENS / "05_discover.png").as_uri())
            .replace("SHOT_COMPARE", (SCREENS / "07_compare.png").as_uri())
        )
        arch_file = STILLS / "architecture_src.html"
        arch_file.write_text(html, encoding="utf-8")
        arch_page.set_viewport_size({"width": 1920, "height": 1080})
        arch_page.goto(arch_file.as_uri(), wait_until="networkidle")
        arch_page.screenshot(path=str(STILLS / "architecture.png"), type="png")
        arch_context.close()
        context.close()
        browser.close()

    broll = DEMO / "assets" / "broll.mp4"
    problem = STILLS / "problem.png"
    if broll.exists():
        subprocess.run(
            [
                FFMPEG, "-y", "-ss", "2.4", "-i", str(broll), "-frames:v", "1",
                "-vf",
                "drawbox=x=48:y=h-120:w=640:h=64:color=0x0b1620@0.88:t=fill,"
                "drawtext=fontfile='C\\:/Windows/Fonts/segoeui.ttf':"
                "text='Illustrative scene, AI-generated':fontcolor=white:"
                "fontsize=28:x=72:y=h-98",
                str(problem),
            ],
            check=True,
        )
        report["problem"] = str(problem)
    else:
        report["problem"] = "missing broll"

    (DEMO / "capture_method.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

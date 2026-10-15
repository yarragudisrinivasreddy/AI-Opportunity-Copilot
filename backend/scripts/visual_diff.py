"""Visual fidelity gate: premium-ui-v2 prototype vs React sample mode.

Writes PNGs + contact sheets + report.json under docs/visual_diff/.

Prep:
  cd design/premium-ui && python -m http.server 8765
  cd frontend && npm run dev -- --port 5173 --host 127.0.0.1
  cd backend && python scripts/visual_diff.py
"""
from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

PROTO = os.environ.get("PROTO_URL", "http://127.0.0.1:8765")
REACT = os.environ.get("REACT_URL", "http://127.0.0.1:5173")
OUT = Path(os.environ.get("OUT_DIR", Path(__file__).resolve().parents[2] / "docs" / "visual_diff"))

PROTO_HASH = {
    "home": "",
    "show": "#/show",
    "understand": "#/understand",
    "discover": "#/discover",
    "brief": "#/brief",
    "compare": "#/compare",
}
LIGHT_SCREENS = list(PROTO_HASH)
VIEWPORTS = [(375, 812), (1280, 800)]


def wait_fonts(page) -> None:
    page.wait_for_timeout(300)
    page.evaluate("() => document.fonts && document.fonts.ready")
    page.wait_for_timeout(200)


def diff_pct(a: Image.Image, b: Image.Image) -> float:
    w, h = min(a.width, b.width), min(a.height, b.height)
    a, b = a.convert("RGB").resize((w, h)), b.convert("RGB").resize((w, h))
    pa, pb = a.load(), b.load()
    bad = 0
    for y in range(h):
        for x in range(w):
            ca, cb = pa[x, y], pb[x, y]
            if abs(ca[0] - cb[0]) + abs(ca[1] - cb[1]) + abs(ca[2] - cb[2]) > 40:
                bad += 1
    return 100.0 * bad / max(w * h, 1)


def contact_sheet(pairs: list[tuple[str, Image.Image, Image.Image]], path: Path) -> None:
    if not pairs:
        return
    gap, label_h = 12, 28
    cell_w = max(max(L.width, R.width) for _, L, R in pairs)
    cell_h = max(max(L.height, R.height) for _, L, R in pairs)
    canvas = Image.new("RGB", (cell_w * 2 + gap * 3, len(pairs) * (cell_h + label_h + gap) + gap), (232, 237, 235))
    draw = ImageDraw.Draw(canvas)
    for i, (name, left, right) in enumerate(pairs):
        y = gap + i * (cell_h + label_h + gap)
        draw.text((gap, y), f"{name} · prototype", fill=(13, 27, 36))
        draw.text((gap * 2 + cell_w, y), f"{name} · react", fill=(13, 27, 36))
        canvas.paste(left.resize((cell_w, cell_h)), (gap, y + label_h))
        canvas.paste(right.resize((cell_w, cell_h)), (gap * 2 + cell_w, y + label_h))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, "PNG")


def shot(page) -> Image.Image:
    wait_fonts(page)
    return Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")


def goto_proto(page, name: str) -> None:
    page.goto(PROTO + "/", wait_until="networkidle")
    h = PROTO_HASH[name]
    if h:
        page.evaluate(f"location.hash = '{h}'")
        page.wait_for_timeout(350)
    wait_fonts(page)


def goto_react(page, name: str) -> None:
    page.goto(REACT, wait_until="networkidle")
    if name == "home":
        return
    if name == "show":
        page.get_by_test_id("start-own").click()
        page.get_by_test_id("show").wait_for()
        return
    page.get_by_test_id("try-sample").click()
    page.get_by_test_id("process-map").wait_for()
    if name == "understand":
        return
    page.get_by_test_id("confirm-map").click()
    page.get_by_test_id("questions").wait_for()
    if name == "questions":
        return
    for _ in range(3):
        skip = page.get_by_test_id("question").locator("button.btn-quiet")
        if skip.count():
            skip.first.click()
            page.wait_for_timeout(200)
    page.get_by_test_id("discover").wait_for()
    if name == "discover":
        return
    page.get_by_test_id("make-brief").click()
    page.get_by_test_id("brief-view").wait_for()
    if name == "brief":
        return
    page.get_by_test_id("to-compare").click()
    page.get_by_test_id("evaluation-view").wait_for()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "notes": [
            "Sample pack wording may differ from prototype placeholders (intentional).",
            "Video uploads: option (a) — MAX_VIDEO_BYTES=25MiB direct HTTP body, under Cloud Run ~32MiB limit; tip asks for 720p 15–30s.",
        ],
        "screens": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for vw, vh in VIEWPORTS:
            pairs = []
            for name in LIGHT_SCREENS:
                ctx = browser.new_context(viewport={"width": vw, "height": vh}, color_scheme="light", device_scale_factor=1)
                page = ctx.new_page()
                goto_proto(page, name)
                left = shot(page)
                ctx.close()

                ctx = browser.new_context(viewport={"width": vw, "height": vh}, color_scheme="light", device_scale_factor=1)
                page = ctx.new_page()
                goto_react(page, name)
                right = shot(page)
                ctx.close()

                key = f"{name}_{vw}_light"
                left.save(OUT / f"{key}_proto.png")
                right.save(OUT / f"{key}_react.png")
                pct = round(diff_pct(left, right), 2)
                pairs.append((key, left, right))
                report["screens"].append({"id": key, "diff_pct": pct})
                print(f"{key}: {pct}%")
            contact_sheet(pairs, OUT / f"contact_{vw}_light.png")

        dark_pairs = []
        for name in ("home", "compare"):
            ctx = browser.new_context(viewport={"width": 375, "height": 812}, color_scheme="dark", device_scale_factor=1)
            page = ctx.new_page()
            goto_proto(page, name)
            left = shot(page)
            ctx.close()
            ctx = browser.new_context(viewport={"width": 375, "height": 812}, color_scheme="dark", device_scale_factor=1)
            page = ctx.new_page()
            goto_react(page, name)
            right = shot(page)
            ctx.close()
            key = f"{name}_375_dark"
            left.save(OUT / f"{key}_proto.png")
            right.save(OUT / f"{key}_react.png")
            pct = round(diff_pct(left, right), 2)
            dark_pairs.append((key, left, right))
            report["screens"].append({"id": key, "diff_pct": pct})
            print(f"{key}: {pct}%")
        contact_sheet(dark_pairs, OUT / "contact_375_dark.png")

        for label, base, name in (("react_home_320", REACT, "home"), ("proto_home_320", PROTO, "home")):
            ctx = browser.new_context(viewport={"width": 320, "height": 640}, color_scheme="light")
            page = ctx.new_page()
            if base == REACT:
                goto_react(page, name)
            else:
                goto_proto(page, name)
            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
            )
            page.screenshot(path=str(OUT / f"{label}.png"), full_page=True)
            report["screens"].append({"id": label, "horizontal_overflow": overflow})
            print(f"{label}: overflow={overflow}")
            ctx.close()

        browser.close()

    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

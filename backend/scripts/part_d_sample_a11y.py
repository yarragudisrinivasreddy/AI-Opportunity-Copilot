"""Part D on SAMPLE path: axe light+dark, keyboard, reduced-motion, 320 overflow en/hi/te.

Writes docs/visual_diff/part_d_sample_a11y.json. Requires Playwright + axe-core CDN.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:5173")
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "part_d_sample_a11y.json"
# Prefer local axe (Hosting CSP blocks CDN script-src).
_AXE_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "frontend" / "node_modules" / "axe-core" / "axe.min.js",
    Path(__file__).resolve().parents[2] / "frontend" / "node_modules" / "axe-core" / "axe.js",
]


def _axe_source() -> str:
    for p in _AXE_CANDIDATES:
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError("axe-core not found under frontend/node_modules; npm i -D axe-core")


def run_axe(page, label: str, scheme: str) -> dict:
    # Hosting CSP blocks script tags; CDP evaluate still loads axe into the page world.
    src = _axe_source()
    page.evaluate(src)
    res = page.evaluate(
        """async () => {
          const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa'] } });
          const bad = r.violations.filter(v => ['serious','critical'].includes(v.impact));
          return {
            violations: bad.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help })),
            all: r.violations.length,
          };
        }"""
    )
    return {"screen": label, "scheme": scheme, **res}


def go_sample_to(page, target: str) -> None:
    page.goto(BASE, wait_until="networkidle")
    if target == "home":
        return
    page.get_by_test_id("try-sample").click()
    # sample-banner is sr-only; wait for process map instead
    page.get_by_test_id("process-map").wait_for()
    if target == "understand":
        return
    page.get_by_test_id("confirm-map").click()
    page.get_by_test_id("questions").wait_for()
    if target == "questions":
        return
    for _ in range(3):
        page.get_by_test_id("question").locator("button.btn-quiet").first.click()
        page.wait_for_timeout(150)
    page.get_by_test_id("discover").wait_for()
    if target == "discover":
        return
    page.locator("[data-testid^='select-opportunity-']").first.click()
    page.get_by_test_id("brief-view").wait_for()
    if target == "brief":
        return
    page.get_by_test_id("to-compare").click()
    page.get_by_test_id("evaluation-view").wait_for()


def main() -> int:
    report: dict = {"base": BASE, "axe": [], "keyboard": {}, "reduced_motion": {}, "overflow_320": []}
    with sync_playwright() as p:
        browser = p.chromium.launch()

        screens = ["home", "understand", "questions", "discover", "brief", "compare"]
        for scheme in ("light", "dark"):
            ctx = browser.new_context(color_scheme=scheme, viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            for screen in screens:
                go_sample_to(page, screen)
                report["axe"].append(run_axe(page, screen, scheme))
            ctx.close()

        # keyboard-only sample journey
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(BASE, wait_until="networkidle")
        # Tab to sample CTA and activate
        reached = False
        for _ in range(40):
            page.keyboard.press("Tab")
            el = page.evaluate(
                """() => {
                  const a = document.activeElement;
                  return a ? { id: a.getAttribute('data-testid'), tag: a.tagName, text: (a.innerText||'').slice(0,40) } : null;
                }"""
            )
            if el and el.get("id") in ("try-sample", "try-sample-2"):
                page.keyboard.press("Enter")
                reached = True
                break
        page.get_by_test_id("process-map").wait_for(timeout=8000)
        page.get_by_test_id("confirm-map").focus()
        page.keyboard.press("Enter")
        page.get_by_test_id("questions").wait_for()
        for _ in range(3):
            page.get_by_test_id("question").locator("button.btn-quiet").first.focus()
            page.keyboard.press("Enter")
            page.wait_for_timeout(120)
        page.get_by_test_id("discover").wait_for()
        page.locator("[data-testid^='select-opportunity-']").first.focus()
        page.keyboard.press("Enter")
        page.get_by_test_id("brief-view").wait_for()
        page.get_by_test_id("to-compare").focus()
        page.keyboard.press("Enter")
        page.get_by_test_id("evaluation-view").wait_for()
        report["keyboard"] = {
            "status": "PASS" if reached else "FAIL",
            "detail": "Tab to Try sample + Enter through confirm/questions/brief/compare",
        }
        ctx.close()

        # reduced motion: CSS animations should be near-zero
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            reduced_motion="reduce",
        )
        page = ctx.new_page()
        go_sample_to(page, "discover")
        anim = page.evaluate(
            """() => {
              const nodes = [...document.querySelectorAll('*')].slice(0, 200);
              let long = 0;
              for (const n of nodes) {
                const s = getComputedStyle(n);
                const dur = s.animationDuration || '0s';
                const td = s.transitionDuration || '0s';
                const parse = (x) => Math.max(0, ...x.split(',').map(v => parseFloat(v)||0));
                if (parse(dur) > 0.05 || parse(td) > 0.05) long++;
              }
              return { elements_with_motion_gt_50ms: long };
            }"""
        )
        report["reduced_motion"] = {
            "status": "PASS" if anim["elements_with_motion_gt_50ms"] <= 5 else "FAIL",
            **anim,
            "detail": "prefers-reduced-motion: reduce; tolerate ≤5 residual transitions",
        }
        ctx.close()

        # 320 overflow en/hi/te on home + compare
        for lang, label in (("en", "English"), ("hi", "हिन्दी"), ("te", "తెలుగు")):
            ctx = browser.new_context(viewport={"width": 320, "height": 640})
            page = ctx.new_page()
            page.goto(BASE, wait_until="networkidle")
            if lang != "en":
                page.get_by_label("Language").select_option(label=label) if page.locator("select").count() else None
                # language control
                sel = page.locator("select").first
                if sel.count():
                    # options by value en/hi/te
                    try:
                        sel.select_option(lang)
                    except Exception:
                        pass
                page.wait_for_timeout(300)
            for screen in ("home", "compare"):
                if screen == "compare":
                    go_sample_to(page, "compare")
                overflow = page.evaluate(
                    """() => {
                      const de = document.documentElement;
                      const body = document.body;
                      return {
                        scrollWidth: Math.max(de.scrollWidth, body.scrollWidth),
                        clientWidth: de.clientWidth,
                        overflow: Math.max(de.scrollWidth, body.scrollWidth) > de.clientWidth + 1,
                      };
                    }"""
                )
                report["overflow_320"].append({"lang": lang, "screen": screen, **overflow})
            ctx.close()

        browser.close()

    serious = sum(len(a["violations"]) for a in report["axe"])
    report["summary"] = {
        "axe_serious_critical_total": serious,
        "axe_status": "PASS" if serious == 0 else "FAIL",
        "keyboard_status": report["keyboard"].get("status"),
        "reduced_motion_status": report["reduced_motion"].get("status"),
        "overflow_status": "PASS" if not any(x["overflow"] for x in report["overflow_320"]) else "FAIL",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("Wrote", OUT)
    return 0 if report["summary"]["axe_status"] == "PASS" and report["summary"]["overflow_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

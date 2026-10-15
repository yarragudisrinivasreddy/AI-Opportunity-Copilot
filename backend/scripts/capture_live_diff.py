"""Capture live ux-preview vs premium-ui prototype screenshots + style audit."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
PROTO = "http://127.0.0.1:8765"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff"
VIEWPORTS = [(375, 812), (1280, 800)]
PROTO_HASH = {
    "home": "#/",
    "show": "#/show",
    "understand": "#/understand",
    "questions": "#/questions",
    "discover": "#/discover",
    "brief": "#/brief",
    "compare": "#/compare",
}
SELECTORS = [".hero h1", ".btn-primary", ".titleblock", ".jstep", ".jhome", ".opp", ".pcard", ".bar"]


def wait_fonts(page) -> None:
    # Live CSP blocks wait_for_function (unsafe-eval). Poll via evaluate instead.
    try:
        for _ in range(40):
            ready = page.evaluate("document.fonts ? document.fonts.status : 'loaded'")
            if ready == "loaded":
                break
            page.wait_for_timeout(100)
    except Exception:
        pass
    page.wait_for_timeout(300)


def unstick(page) -> None:
    """Avoid sticky header/confirm duplication in full_page screenshots."""
    try:
        page.add_style_tag(content=".bar,.confirm{position:static!important;bottom:auto!important}")
    except Exception:
        pass


def style_dump(page, sels: list[str]) -> dict:
    return page.evaluate(
        """(sels) => {
          const props = ['fontFamily','fontSize','fontStretch','color','backgroundColor','padding','borderRadius'];
          const out = {};
          for (const s of sels) {
            const el = document.querySelector(s);
            if (!el) { out[s] = null; continue; }
            const cs = getComputedStyle(el);
            out[s] = Object.fromEntries(props.map(p => [p, cs[p]]));
          }
          out._fonts = [...document.fonts].map(f => ({family:f.family, status:f.status, stretch:f.stretch, weight:f.weight}));
          out._archivo = [...document.fonts].some(f => /archivo/i.test(f.family) && f.status === 'loaded');
          return out;
        }""",
        sels,
    )


def side_by_side(proto_path: Path, live_path: Path, out: Path) -> None:
    from PIL import Image

    a = Image.open(proto_path).convert("RGB")
    b = Image.open(live_path).convert("RGB")
    h = max(a.height, b.height)
    canvas = Image.new("RGB", (a.width + b.width + 16, h), (240, 240, 240))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.width + 16, 0))
    canvas.save(out)


def goto_proto(page, name: str) -> None:
    page.goto(PROTO, wait_until="networkidle")
    page.evaluate(f"location.hash = '{PROTO_HASH[name]}'")
    page.wait_for_timeout(400)
    wait_fonts(page)


def skip_questions(page) -> None:
    page.get_by_test_id("questions").wait_for(timeout=15000)
    for _ in range(3):
        btn = page.get_by_test_id("question").locator("button.btn-quiet")
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(250)


def goto_live(page, name: str) -> None:
    page.goto(LIVE, wait_until="networkidle")
    # bust SW / cache
    page.evaluate("""async () => {
      if (navigator.serviceWorker) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.map(r => r.unregister()));
      }
      if (window.caches) {
        const keys = await caches.keys();
        await Promise.all(keys.map(k => caches.delete(k)));
      }
    }""")
    page.reload(wait_until="networkidle")
    wait_fonts(page)
    if name == "home":
        return
    if name == "show":
        page.get_by_test_id("start-own").click()
        page.get_by_test_id("show").wait_for()
        wait_fonts(page)
        return
    page.get_by_test_id("try-sample").click()
    page.get_by_test_id("process-map").wait_for(timeout=60000)
    if name == "understand":
        wait_fonts(page)
        return
    page.get_by_test_id("confirm-map").click()
    if name == "questions":
        page.get_by_test_id("questions").wait_for()
        wait_fonts(page)
        return
    skip_questions(page)
    page.get_by_test_id("discover").wait_for()
    if name == "discover":
        wait_fonts(page)
        return
    page.get_by_test_id("make-brief").click()
    page.get_by_test_id("brief-view").wait_for()
    if name == "brief":
        wait_fonts(page)
        return
    page.get_by_test_id("to-compare").click()
    page.get_by_test_id("evaluation-view").wait_for()
    wait_fonts(page)


def network_audit(page) -> dict:
    failed = []
    csp = []

    def on_resp(r):
        if r.status >= 400 and ("/fonts/" in r.url or "/img/" in r.url or r.url.endswith(".css") or r.url.endswith(".js")):
            failed.append({"url": r.url, "status": r.status})

    def on_console(m):
        t = m.text
        if "Content Security Policy" in t or m.type == "error":
            csp.append({"type": m.type, "text": t})

    page.on("response", on_resp)
    page.on("console", on_console)
    return {"failed": failed, "console": csp}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    screens = ["home", "show", "understand", "questions", "discover", "brief", "compare"]
    report: dict = {"bundle": {}, "styles": {}, "network": {}, "screens": []}

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Bundle / network / style audit at 1280 home
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
        page = ctx.new_page()
        net = {"failed": [], "console": []}

        def on_resp(r):
            if r.status >= 400:
                net["failed"].append({"url": r.url, "status": r.status})

        def on_console(m):
            if "Content Security Policy" in m.text or m.type == "error":
                net["console"].append({"type": m.type, "text": m.text})

        page.on("response", on_resp)
        page.on("console", on_console)
        page.goto(LIVE, wait_until="networkidle")
        page.evaluate("""async () => {
          if (navigator.serviceWorker) {
            const regs = await navigator.serviceWorker.getRegistrations();
            await Promise.all(regs.map(r => r.unregister()));
          }
        }""")
        page.reload(wait_until="networkidle")
        wait_fonts(page)
        report["bundle"] = page.evaluate("""() => ({
          css: [...document.styleSheets].map(s => s.href).filter(Boolean),
          scripts: [...document.scripts].map(s => s.src).filter(Boolean),
          sw: !!navigator.serviceWorker?.controller,
        })""")
        report["network"] = net
        report["styles"]["live_home"] = style_dump(page, SELECTORS)
        ctx.close()

        ctxp = browser.new_context(viewport={"width": 1280, "height": 800})
        pagep = ctxp.new_page()
        goto_proto(pagep, "home")
        report["styles"]["proto_home"] = style_dump(pagep, SELECTORS)
        ctxp.close()

        for vw, vh in VIEWPORTS:
            for name in screens:
                # proto
                c1 = browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1)
                p1 = c1.new_page()
                goto_proto(p1, name)
                if name in ("understand", "discover", "brief", "compare", "questions"):
                    # full page
                    pass
                proto_path = OUT / f"live_{name}_{vw}_proto.png"
                unstick(p1)
                p1.screenshot(path=str(proto_path), full_page=True)
                if name == "home":
                    report["styles"][f"proto_{name}_{vw}"] = style_dump(p1, SELECTORS)
                c1.close()

                # live
                c2 = browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1, ignore_https_errors=True)
                p2 = c2.new_page()
                goto_live(p2, name)
                live_path = OUT / f"live_{name}_{vw}_live.png"
                unstick(p2)
                p2.screenshot(path=str(live_path), full_page=True)
                if name in ("home", "understand", "discover", "compare"):
                    report["styles"][f"live_{name}_{vw}"] = style_dump(p2, SELECTORS)
                c2.close()

                side = OUT / f"live_{name}_{vw}_side.png"
                try:
                    side_by_side(proto_path, live_path, side)
                except Exception as e:
                    report.setdefault("side_errors", []).append(str(e))
                report["screens"].append({"name": name, "w": vw, "proto": str(proto_path.name), "live": str(live_path.name), "side": str(side.name)})
                print("OK", name, vw)

            # Telugu home
            for label, url, nav in (
                ("proto", PROTO, lambda pg: (pg.goto(PROTO, wait_until="networkidle"), pg.evaluate("location.hash='#/'"), pg.select_option("#lang", "te") if pg.locator("#lang").count() else None)),
            ):
                pass
            c3 = browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1)
            p3 = c3.new_page()
            p3.goto(PROTO, wait_until="networkidle")
            p3.evaluate("location.hash='#/'")
            if p3.locator("#lang").count():
                p3.select_option("#lang", "te")
            wait_fonts(p3)
            p3.wait_for_timeout(400)
            te_proto = OUT / f"live_home_te_{vw}_proto.png"
            unstick(p3)
            p3.screenshot(path=str(te_proto), full_page=True)
            c3.close()

            c4 = browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1, ignore_https_errors=True)
            p4 = c4.new_page()
            p4.goto(LIVE, wait_until="networkidle")
            p4.get_by_test_id("lang").select_option("te")
            wait_fonts(p4)
            p4.wait_for_timeout(400)
            te_live = OUT / f"live_home_te_{vw}_live.png"
            unstick(p4)
            p4.screenshot(path=str(te_live), full_page=True)
            c4.close()
            te_side = OUT / f"live_home_te_{vw}_side.png"
            try:
                side_by_side(te_proto, te_live, te_side)
            except Exception as e:
                report.setdefault("side_errors", []).append(str(e))
            report["screens"].append({"name": "home_te", "w": vw, "proto": te_proto.name, "live": te_live.name, "side": te_side.name})
            print("OK home_te", vw)

        browser.close()

    (OUT / "live_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote", OUT / "live_audit.json")


if __name__ == "__main__":
    main()

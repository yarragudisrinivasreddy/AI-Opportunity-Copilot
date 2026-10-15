"""Overflow check at 320/375 (en/hi/te) + own-process capture on live preview."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Avoid Windows console UnicodeEncodeError on Indic step labels.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff"
# Legacy phrase must not appear after the flow fallback change.
LEGACY_SYNTH = "captured once upstream"

DESC_EN = (
    "Every morning trucks arrive with steel wire and bar stock. "
    "Security writes the vehicle in a paper register. "
    "The store clerk matches the delivery challan to the purchase order by hand. "
    "An inspector measures five pieces with a vernier caliper and writes readings on a printed sheet. "
    "At the end of the day someone types the sheet into Excel. "
    "If a lot fails, the supervisor is phoned and the lot is tagged."
)

DESC_TE = 'ప్రతి ఉదయం ట్రక్కులు స్టీల్ వైర్ మరియు బార్ స్టాక్\u200cతో వస్తాయి. సెక్యూరిటీ వాహనాన్ని కాగిత రిజిస్టర్\u200cలో రాస్తారు. స్టోర్ క్లర్క్ డెలివరీ చలాన్ను కొనుగోలు ఆర్డర్\u200cతో చేతితో సరిపోల్చుతారు. ఇన్స్పెక్టర్ వెర్నియర్ కాలిపర్\u200cతో ఐదు ముక్కలు కొలిచి ప్రింటెడ్ షీట్\u200cపై రాస్తారు. రోజు చివర ఎవరో షీట్\u200cను ఎక్సెల్\u200cలో టైప్ చేస్తారు. లాట్ ఫెయిల్ అయితే సూపర్వైజర్\u200cకు ఫోన్ చేసి ట్యాగ్ చేస్తారు.'

ANSWERS = {
    "en": ["About 40 a day", "15 minutes", "Supervisor decides", "Excel and paper sheets", "Paper and Excel"],
    "te": ['రోజుకు సుమారు 40', '15 నిమిషాలు', 'సూపర్వైజర్ నిర్ణయం', 'ఎక్సెల్ మరియు కాగితం', 'కాగితం మరియు ఎక్సెల్'],
}


def overflow(page) -> dict:
    return page.evaluate(
        """() => {
          const doc = document.documentElement;
          const body = document.body;
          const sw = Math.max(doc.scrollWidth, body.scrollWidth);
          const cw = doc.clientWidth;
          const brand = document.querySelector('.brand');
          const lang = document.querySelector('.lang');
          const nav = document.querySelector('#nav');
          const navDisplay = nav ? getComputedStyle(nav).display : null;
          const stepEl = document.querySelector('.titleblock > div:last-child strong');
          const stepText = (stepEl && stepEl.textContent.trim())
            || [...document.querySelectorAll('.titleblock strong')].map(e => e.textContent).join(' | ');
          return {
            overflow: sw > cw + 1,
            scrollWidth: sw,
            clientWidth: cw,
            navDisplay,
            brandText: brand && brand.textContent.trim().slice(0, 40),
            langVisible: !!(lang && getComputedStyle(lang).display !== 'none'),
            stepText,
          };
        }"""
    )


def unstick(page) -> None:
    try:
        page.add_style_tag(content=".bar,.confirm{position:static!important}")
    except Exception:
        pass


def read_process_steps(page) -> list[str]:
    return page.evaluate(
        """() => [...document.querySelectorAll('.route .step h3, .route textarea')]
          .map(el => (el.value || el.textContent || '').trim())
          .filter(Boolean)"""
    )


def flow_audit(page, process_steps: list[str] | None = None) -> dict:
    return page.evaluate(
        """({ legacy, steps }) => {
          const todays = [...document.querySelectorAll('.fcell.today span')].map(el => el.textContent.trim());
          const afters = [...document.querySelectorAll('.fcell.after span:last-child')].map(el => el.textContent.trim());
          const stepList = (steps || []).map(s => s.toLowerCase());
          const overlap = (a, b) => {
            const aa = a.toLowerCase(); const bb = b.toLowerCase();
            if (!aa || !bb) return false;
            if (aa.includes(bb.slice(0, 24)) || bb.includes(aa.slice(0, 24))) return true;
            const aw = aa.split(/\\s+/).filter(w => w.length > 4);
            return aw.filter(w => bb.includes(w)).length >= 2;
          };
          let grounded = 0;
          for (const t of todays) {
            if (stepList.some(s => overlap(t, s))) grounded += 1;
          }
          const legacyHits = afters.filter(a => a.toLowerCase().includes(legacy)).length;
          const coveredBy = afters.filter(a => a.toLowerCase().includes('covered by:')).length;
          return {
            stepCount: stepList.length,
            flowRowCount: todays.length,
            groundedTodayCount: grounded,
            groundedRatio: todays.length ? grounded / todays.length : null,
            legacySynthPhraseCount: legacyHits,
            coveredByPhraseCount: coveredBy,
            todaysSample: todays.slice(0, 3),
            aftersSample: afters.slice(0, 3),
          };
        }""",
        {"legacy": LEGACY_SYNTH, "steps": process_steps or []},
    )


def run_own(page, lang: str, desc: str, tag: str, report: dict) -> None:
    discover_payload: dict = {}

    def on_response(resp) -> None:
        try:
            if "/discover" in resp.url and resp.request.method == "POST" and resp.ok:
                discover_payload.update(resp.json())
        except Exception:
            pass

    page.on("response", on_response)
    page.goto(LIVE, wait_until="networkidle")
    page.get_by_test_id("lang").select_option(lang)
    page.wait_for_timeout(300)
    page.get_by_test_id("start-own").click()
    page.get_by_test_id("show").wait_for()
    page.get_by_test_id("desc").fill(desc)
    page.get_by_test_id("analyse").click()
    try:
        page.get_by_test_id("busy-popup").wait_for(timeout=8000)
        report.setdefault(tag, {})["busy_popup"] = True
    except Exception:
        report.setdefault(tag, {})["busy_popup"] = False
    page.get_by_test_id("process-map").wait_for(timeout=180_000)
    # step counter should be 2 of 5 on understand
    report.setdefault(tag, {})["step_on_understand"] = page.evaluate(
        """() => document.querySelector('.titleblock > div:last-child strong')?.textContent?.trim() || ''"""
    )
    process_steps = read_process_steps(page)
    report.setdefault(tag, {})["process_steps"] = process_steps[:8]
    unstick(page)
    page.screenshot(path=str(OUT / f"own_{tag}_understand.png"), full_page=True)

    page.get_by_test_id("confirm-map").click()
    # Confirm saves async — wait for either follow-up questions or Find.
    page.wait_for_function(
        """() => {
          const find = document.querySelector('[data-testid=find-opportunities]');
          const ans = document.querySelector('[data-testid=answer-input]');
          const err = document.querySelector('[data-testid=error-banner]');
          return !!(find || ans || err);
        }""",
        timeout=90_000,
    )
    labels = []
    question_texts = []
    for i in range(5):
        if page.get_by_test_id("error-banner").count():
            raise RuntimeError(page.get_by_test_id("error-banner").inner_text()[:300])
        if page.get_by_test_id("find-opportunities").count() and page.get_by_test_id("find-opportunities").is_visible():
            break
        if not page.get_by_test_id("answer-input").count():
            break
        page.get_by_test_id("answer-input").wait_for(timeout=90_000)
        if page.locator("[data-testid=q-of]").count():
            labels.append(page.locator("[data-testid=q-of]").inner_text())
        elif page.locator(".q-meta span").count():
            labels.append(page.locator(".q-meta span").first.inner_text())
        if page.locator("#qh").count():
            question_texts.append(page.locator("#qh").inner_text())
        page.get_by_test_id("answer-input").fill(ANSWERS[lang][min(i, len(ANSWERS[lang]) - 1)])
        page.get_by_test_id("answer").click()
        page.wait_for_function(
            """() => {
              const busy = document.querySelector('[data-testid=busy-popup]');
              const find = document.querySelector('[data-testid=find-opportunities]');
              const ans = document.querySelector('[data-testid=answer-input]');
              return !busy && !!(find || ans);
            }""",
            timeout=90_000,
        )
    report.setdefault(tag, {})["question_labels"] = labels
    report.setdefault(tag, {})["question_texts"] = question_texts

    page.get_by_test_id("find-opportunities").click()
    try:
        page.get_by_test_id("busy-popup").wait_for(timeout=5000)
    except Exception:
        pass
    page.get_by_test_id("discover").wait_for(timeout=300_000)
    page.get_by_test_id("flow").wait_for()
    report.setdefault(tag, {})["flow"] = flow_audit(page, process_steps)
    report.setdefault(tag, {})["flowAuditApi"] = discover_payload.get("flowAudit") or []
    report.setdefault(tag, {})["step_on_discover"] = page.evaluate(
        """() => document.querySelector('.titleblock > div:last-child strong')?.textContent?.trim() || ''"""
    )
    unstick(page)
    page.screenshot(path=str(OUT / f"own_{tag}_discover.png"), full_page=True)

    # Visible "Write the brief" on first card selects it; sr select-* can be covered by .hint.
    page.get_by_test_id("opp-A").locator("button.btn").first.click()
    page.get_by_test_id("make-brief").wait_for(timeout=30_000)
    page.get_by_test_id("make-brief").click()
    try:
        page.get_by_test_id("busy-popup").wait_for(timeout=5000)
    except Exception:
        pass
    page.get_by_test_id("brief-view").wait_for(timeout=180_000)
    unstick(page)
    page.screenshot(path=str(OUT / f"own_{tag}_brief.png"), full_page=True)

    page.get_by_test_id("to-compare").click()
    if page.get_by_test_id("seed-proposals").count() and page.get_by_test_id("seed-proposals").is_visible():
        page.get_by_test_id("seed-proposals").click()
    # Seed now auto-evaluates; evaluate button is only if seed left proposals unscored.
    if page.get_by_test_id("evaluate").count() and page.get_by_test_id("evaluate").is_visible():
        page.get_by_test_id("evaluate").click()
    page.get_by_test_id("evaluation-view").wait_for(timeout=180_000)
    unstick(page)
    page.screenshot(path=str(OUT / f"own_{tag}_compare.png"), full_page=True)
    report.setdefault(tag, {})["screens"] = [
        f"own_{tag}_understand.png",
        f"own_{tag}_discover.png",
        f"own_{tag}_brief.png",
        f"own_{tag}_compare.png",
    ]


def main() -> None:
    import os

    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"overflow": [], "own": {}}
    skip_overflow = os.environ.get("OWN_ONLY", "").strip() in ("1", "true", "yes")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        if not skip_overflow:
            for w in (320, 375):
                for lang in ("en", "hi", "te"):
                    ctx = browser.new_context(viewport={"width": w, "height": 720}, device_scale_factor=1)
                    page = ctx.new_page()
                    page.goto(LIVE, wait_until="networkidle")
                    page.get_by_test_id("lang").select_option(lang)
                    page.wait_for_timeout(400)
                    info = overflow(page)
                    info.update({"w": w, "lang": lang, "screen": "home"})
                    report["overflow"].append(info)
                    print("overflow", w, lang, info["overflow"], "nav=", info["navDisplay"])
                    page.get_by_test_id("start-own").click()
                    page.get_by_test_id("show").wait_for()
                    info2 = overflow(page)
                    info2.update({"w": w, "lang": lang, "screen": "show"})
                    report["overflow"].append(info2)
                    print("overflow show", w, lang, info2["overflow"], "step=", info2.get("stepText"))
                    ctx.close()

        for lang, desc, tag in (("en", DESC_EN, "en"), ("te", DESC_TE, "te")):
            ctx = browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
            page = ctx.new_page()
            try:
                run_own(page, lang, desc, tag, report["own"])
                print("OWN OK", tag, report["own"].get(tag, {}).get("flow"))
            except Exception as e:
                report["own"].setdefault(tag, {})["error"] = str(e)
                print("OWN FAIL", tag, e)
                try:
                    page.screenshot(path=str(OUT / f"own_{tag}_error.png"), full_page=True)
                except Exception:
                    pass
            ctx.close()
        browser.close()

    cases = [v for v in report["own"].values() if "error" not in v]
    api_rows = [row for c in cases for row in (c.get("flowAuditApi") or [])]
    report["synthesize_summary"] = {
        "cases_run": len(cases),
        "opportunities": len(api_rows),
        "grounded_kept_total": sum(r.get("groundedKept", 0) for r in api_rows),
        "ungrounded_dropped_total": sum(r.get("ungroundedDropped", 0) for r in api_rows),
        "synth_fired_count": sum(1 for r in api_rows if r.get("synthesized")),
        "legacy_phrase_hits": sum((c.get("flow") or {}).get("legacySynthPhraseCount", 0) for c in cases),
        "per_case": {
            k: {
                "flowAuditApi": v.get("flowAuditApi"),
                "ui_grounded": (v.get("flow") or {}).get("groundedTodayCount"),
                "ui_rows": (v.get("flow") or {}).get("flowRowCount"),
                "question_texts": v.get("question_texts"),
            }
            for k, v in report["own"].items()
        },
        "note": "flowAuditApi from discover; synthesized=true only when <3 grounded rows remained",
    }
    (OUT / "own_path_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["synthesize_summary"], indent=2))
    print("Wrote", OUT / "own_path_audit.json")


if __name__ == "__main__":
    main()

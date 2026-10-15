"""One live own-process run: time discover+evaluate, seed 5x flag probe, CSP/console check."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
API = "https://opportunity-copilot-api-814609847961.us-central1.run.app"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "round3_timing_flags.json"
CLEAN = {"p_visionworks", "p_leanbuild", "p_docuflow"}
DESC = (
    "Every morning trucks arrive with steel wire and bar stock. "
    "Security writes the vehicle in a paper register. "
    "The store clerk matches the delivery challan to the purchase order by hand. "
    "An inspector measures five pieces with a vernier caliper and writes readings on a printed sheet. "
    "At the end of the day someone types the sheet into Excel. "
    "If a lot fails, the supervisor is phoned and the lot is tagged."
)


def bearer_from_storage(page) -> str | None:
    return page.evaluate(
        """() => {
          for (const k of Object.keys(localStorage)) {
            if (k.startsWith('firebase:authUser:')) {
              try {
                const o = JSON.parse(localStorage.getItem(k));
                if (o?.stsTokenManager?.accessToken) return o.stsTokenManager.accessToken;
              } catch (e) {}
            }
          }
          return null;
        }"""
    )


def main() -> None:
    timings: dict = {}
    console_errors: list[str] = []
    api_timings: dict[str, float] = {}
    case_id = None
    runs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda e: console_errors.append(f"pageerror:{e}"))
        page.on(
            "console",
            lambda m: console_errors.append(f"console:{m.text}") if m.type == "error" else None,
        )

        pending: dict[str, float] = {}

        def on_req(req):
            if "/api/" in req.url and req.method == "POST":
                pending[req.url] = time.perf_counter()

        def on_resp(resp):
            nonlocal case_id
            try:
                u = resp.url
                if u in pending:
                    dur = time.perf_counter() - pending.pop(u)
                    if "/discover" in u:
                        api_timings["discover_api_s"] = round(dur, 1)
                    elif "/evaluate" in u:
                        api_timings["evaluate_api_s"] = round(dur, 1)
                    elif "/analyze" in u:
                        api_timings["analyze_api_s"] = round(dur, 1)
                    elif "/brief" in u and "/proposals" not in u:
                        api_timings["brief_api_s"] = round(dur, 1)
                if "/api/cases/" in u:
                    parts = u.split("/api/cases/")
                    cid = parts[1].split("/")[0].split("?")[0]
                    if len(cid) >= 8:
                        case_id = cid
            except Exception:
                pass

        page.on("request", on_req)
        page.on("response", on_resp)

        page.goto(LIVE, wait_until="networkidle")
        # Fetch CSP from document response headers via navigation
        csp_header = page.evaluate(
            """async () => {
              const r = await fetch(location.href, { method: 'HEAD' }).catch(() => null);
              if (!r) return '';
              return r.headers.get('content-security-policy') || '';
            }"""
        )
        # Also parse from a GET
        if not csp_header:
            csp_header = page.evaluate(
                """async () => {
                  const r = await fetch(location.origin + '/', { cache: 'no-store' });
                  return r.headers.get('content-security-policy') || '';
                }"""
            )

        page.get_by_test_id("lang").select_option("en")
        page.get_by_test_id("start-own").click()
        page.get_by_test_id("desc").fill(DESC)
        t0 = time.perf_counter()
        page.get_by_test_id("analyse").click()
        page.get_by_test_id("process-map").wait_for(timeout=180_000)
        timings["analyze_ui_s"] = round(time.perf_counter() - t0, 1)
        page.get_by_test_id("confirm-map").click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=answer-input],[data-testid=find-opportunities]')",
            timeout=90_000,
        )
        for ans in ("About 40 a day", "15 minutes", "Supervisor decides", "Excel and paper", "Paper and Excel"):
            if page.get_by_test_id("find-opportunities").count() and page.get_by_test_id(
                "find-opportunities"
            ).is_visible():
                break
            if not page.get_by_test_id("answer-input").count():
                break
            page.get_by_test_id("answer-input").fill(ans)
            page.get_by_test_id("answer").click()
            page.wait_for_function(
                "() => !document.querySelector('[data-testid=busy-popup]')",
                timeout=90_000,
            )
        t1 = time.perf_counter()
        page.get_by_test_id("find-opportunities").click()
        page.get_by_test_id("opp-A").wait_for(timeout=180_000)
        timings["discover_ui_s"] = round(time.perf_counter() - t1, 1)
        page.locator("[data-testid^='select-opportunity-']").first.click()
        if page.get_by_test_id("brief-options").count():
            page.get_by_test_id("brief-options").wait_for(timeout=30_000)
            page.get_by_test_id("target-weeks").fill("12")
            page.get_by_test_id("budget-low").fill("800000")
            page.get_by_test_id("budget-high").fill("1200000")
        page.get_by_test_id("make-brief").click()
        page.get_by_test_id("brief-view").wait_for(timeout=180_000)
        page.get_by_test_id("to-compare").click()
        page.get_by_test_id("proposals").wait_for(timeout=60_000)
        assert case_id, "case id missing"
        token = bearer_from_storage(page)
        assert token, "no firebase token"

        for i in range(5):
            t2 = time.perf_counter()
            row = page.evaluate(
                """async ({ api, caseId, token }) => {
                  const headers = {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token,
                  };
                  const seed = await fetch(api + '/api/cases/' + caseId + '/proposals/seed', {
                    method: 'POST', headers,
                  });
                  const t0 = performance.now();
                  const evRes = await fetch(api + '/api/cases/' + caseId + '/evaluate', {
                    method: 'POST', headers, body: JSON.stringify({}),
                  });
                  const body = await evRes.json().catch(() => ({}));
                  return {
                    seedStatus: seed.status,
                    evalStatus: evRes.status,
                    evaluate_ms: Math.round(performance.now() - t0),
                    flags: body?.data?.flags || [],
                    extracted: (body?.data?.extracted || []).map(e => ({
                      id: e.proposal_id,
                      detected: !!e.injection_flag?.detected,
                      reasons: e.injection_flag?.reasons || [],
                    })),
                    ranking: body?.data?.ranking || [],
                  };
                }""",
                {"api": API, "caseId": case_id, "token": token},
            )
            token = bearer_from_storage(page) or token
            if i == 0:
                timings["evaluate_direct_s"] = round(row.get("evaluate_ms", 0) / 1000, 1)
            clean_hard = [e["id"] for e in row["extracted"] if e["id"] in CLEAN and e["detected"]]
            lean_reasons = next(
                (e["reasons"] for e in row["extracted"] if e["id"] == "p_leanbuild"), []
            )
            runs.append({
                "n": i + 1,
                "flags": row["flags"],
                "clean_hard_flagged": clean_hard,
                "leanbuild_reasons": lean_reasons,
                "leanbuild_detected": any(
                    e["id"] == "p_leanbuild" and e["detected"] for e in row["extracted"]
                ),
                "ranking": row["ranking"],
                "statuses": {"seed": row["seedStatus"], "eval": row["evalStatus"]},
                "wall_s": round(time.perf_counter() - t2, 1),
            })
            print("run", i + 1, runs[-1])

        # UI seed path for screenshots
        page.get_by_test_id("seed-proposals").click()
        page.get_by_test_id("evaluation-view").wait_for(timeout=300_000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT.parent / "round3_compare_live_1280.png"), full_page=True)
        page.set_viewport_size({"width": 375, "height": 900})
        page.screenshot(path=str(OUT.parent / "round3_compare_live_375.png"), full_page=True)
        browser.close()

    hard_n = sum(1 for r in runs if r["clean_hard_flagged"])
    lean_hard_n = sum(1 for r in runs if r["leanbuild_detected"])
    out = {
        "case_id": case_id,
        "timings_s": {**timings, **api_timings},
        "console_errors": console_errors[:20],
        "csp_header": csp_header,
        "api_host": API,
        "runs": runs,
        "summary": {
            "seed_runs": len(runs),
            "clean_hard_flagged_runs": hard_n,
            "leanbuild_hard_flagged_runs": lean_hard_n,
            "rule": "Hard flag = injection.scan only; model_detected is advisory",
        },
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "timings_s": out["timings_s"],
        "summary": out["summary"],
        "console_errors": console_errors[:5],
        "csp_header": csp_header[:200],
    }, indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

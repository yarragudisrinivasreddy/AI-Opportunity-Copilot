"""Seed+evaluate 5 times on ux-preview; report clean-proposal false flags."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
API = "https://opportunity-copilot-api-814609847961.us-central1.run.app"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "seed_flag_probe.json"
CLEAN = {"p_visionworks", "p_leanbuild", "p_docuflow"}
DESC = (
    "Every morning trucks arrive with steel wire and bar stock. "
    "Security writes the vehicle in a paper register. "
    "The store clerk matches the delivery challan to the purchase order by hand. "
    "An inspector measures five pieces with a vernier caliper and writes readings on a printed sheet. "
    "At the end of the day someone types the sheet into Excel. "
    "If a lot fails, the supervisor is phoned and the lot is tagged."
)


def drive_to_brief(page) -> str:
    page.goto(LIVE, wait_until="networkidle")
    page.get_by_test_id("lang").select_option("en")
    page.get_by_test_id("start-own").click()
    page.get_by_test_id("desc").fill(DESC)
    page.get_by_test_id("analyse").click()
    page.get_by_test_id("process-map").wait_for(timeout=180_000)
    page.get_by_test_id("confirm-map").click()
    page.wait_for_function(
        "() => document.querySelector('[data-testid=answer-input],[data-testid=find-opportunities]')",
        timeout=90_000,
    )
    for ans in ("About 40 a day", "15 minutes", "Supervisor decides", "Excel and paper", "Paper and Excel"):
        if page.get_by_test_id("find-opportunities").count() and page.get_by_test_id("find-opportunities").is_visible():
            break
        if not page.get_by_test_id("answer-input").count():
            break
        page.get_by_test_id("answer-input").fill(ans)
        page.get_by_test_id("answer").click()
        page.wait_for_function(
            "() => !document.querySelector('[data-testid=busy-popup]')",
            timeout=90_000,
        )
    page.get_by_test_id("find-opportunities").click()
    page.get_by_test_id("opp-A").wait_for(timeout=180_000)
    page.get_by_test_id("opp-A").locator("button.btn").first.click()
    page.get_by_test_id("make-brief").click()
    page.get_by_test_id("brief-view").wait_for(timeout=180_000)
    page.get_by_test_id("to-compare").click()
    page.get_by_test_id("proposals").wait_for(timeout=60_000)
    return page.evaluate(
        """() => {
          const m = location.href.match(/cases?\\/([a-f0-9]+)/i);
          if (m) return m[1];
          try {
            const raw = localStorage.getItem('copilot-case') || sessionStorage.getItem('copilot-case');
            if (raw) return JSON.parse(raw).id || '';
          } catch (e) {}
          const el = document.querySelector('[data-case-id]');
          return el?.getAttribute('data-case-id') || '';
        }"""
    )


def seed_eval(page, case_id: str) -> dict:
    return page.evaluate(
        """async ({ api, caseId }) => {
          const token = await window.firebaseAuth?.currentUser?.getIdToken?.()
            || await (async () => {
              // fallback: grab from last Authorization via firebase modular if exposed
              const keys = Object.keys(window);
              return null;
            })();
          // Prefer same-origin rewrite so cookies/auth from the app apply via fetch interceptor
          const base = api;
          const auth = localStorage.getItem('firebase:authUser') || '';
          let bearer = null;
          try {
            const u = Object.values(JSON.parse(localStorage.getItem(
              Object.keys(localStorage).find(k => k.startsWith('firebase:authUser')) || ''
            ) || '{}'));
          } catch (e) {}
          // Use the app's own fetch path: click is heavier; read token from indexed path
          const mod = await import('https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js').catch(() => null);
          // Simplest reliable path: call through page's existing session by using relative /api
          const headers = { 'Content-Type': 'application/json' };
          // Pull token from Firebase Auth persistence
          for (const k of Object.keys(localStorage)) {
            if (k.startsWith('firebase:authUser:')) {
              try {
                const o = JSON.parse(localStorage.getItem(k));
                bearer = o?.stsTokenManager?.accessToken || null;
              } catch (e) {}
            }
          }
          if (bearer) headers['Authorization'] = 'Bearer ' + bearer;
          const seed = await fetch(base + '/api/cases/' + caseId + '/proposals/seed', {
            method: 'POST', headers,
          });
          const seedBody = await seed.text();
          const ev = await fetch(base + '/api/cases/' + caseId + '/evaluate', {
            method: 'POST', headers, body: JSON.stringify({}),
          });
          const evBody = await ev.json();
          return {
            seedStatus: seed.status,
            evalStatus: ev.status,
            flags: evBody?.data?.flags || [],
            extracted: (evBody?.data?.extracted || []).map(e => ({
              id: e.proposal_id,
              detected: e.injection_flag?.detected,
              reasons: e.injection_flag?.reasons || [],
            })),
          };
        }""",
        {"api": API, "caseId": case_id},
    )


def main() -> None:
    runs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        # Drive once to brief, then seed/eval 5 times on same case (re-seed overwrites).
        page.goto(LIVE, wait_until="networkidle")
        # Get case id from App state via UI flow + network
        case_id_holder: dict = {"id": None}

        def on_resp(resp):
            try:
                u = resp.url
                if "/api/cases/" in u and resp.request.method in ("POST", "PUT", "GET"):
                    parts = u.split("/api/cases/")
                    if len(parts) > 1:
                        cid = parts[1].split("/")[0].split("?")[0]
                        if len(cid) >= 8 and case_id_holder["id"] is None:
                            case_id_holder["id"] = cid
            except Exception:
                pass

        page.on("response", on_resp)
        drive_to_brief(page)
        case_id = case_id_holder["id"]
        if not case_id:
            raise SystemExit("no case id captured")
        print("case", case_id)
        for i in range(5):
            row = seed_eval(page, case_id)
            clean_flagged = [
                e for e in row.get("extracted", [])
                if e["id"] in CLEAN and e.get("detected")
            ]
            model_only = [
                e for e in row.get("extracted", [])
                if e["id"] in CLEAN and not e.get("detected") and "model_detected" in (e.get("reasons") or [])
            ]
            runs.append({
                "n": i + 1,
                "flags": row.get("flags"),
                "extracted": row.get("extracted"),
                "clean_hard_flagged": [e["id"] for e in clean_flagged],
                "clean_model_advisory": [e["id"] for e in model_only],
                "statuses": {"seed": row.get("seedStatus"), "eval": row.get("evalStatus")},
            })
            print(
                f"run {i+1}: hard_clean={runs[-1]['clean_hard_flagged']} "
                f"model_adv={runs[-1]['clean_model_advisory']} flags={row.get('flags')}"
            )
        browser.close()
    hard_n = sum(1 for r in runs if r["clean_hard_flagged"])
    model_n = sum(1 for r in runs if "p_leanbuild" in r["clean_model_advisory"] or "p_leanbuild" in r["clean_hard_flagged"])
    out = {
        "runs": runs,
        "summary": {
            "n": len(runs),
            "clean_hard_flagged_runs": hard_n,
            "leanbuild_model_or_hard_runs": model_n,
            "note": "Hard flag = rule scan. model_detected alone is advisory after fix.",
        },
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()

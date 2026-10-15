"""Own-process Compare on ux-preview (EN): screenshots + real Vertex scores from the UI/API."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIVE = "https://y-srinivasreddy--ux-preview-aspk3ryv.web.app"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff"

DESC = (
    "Every morning trucks arrive with steel wire and bar stock. "
    "Security writes the vehicle in a paper register. "
    "The store clerk matches the delivery challan to the purchase order by hand. "
    "An inspector measures five pieces with a vernier caliper and writes readings on a printed sheet. "
    "At the end of the day someone types the sheet into Excel. "
    "If a lot fails, the supervisor is phoned and the lot is tagged."
)


def drive_to_compare(page) -> dict:
    api_hits: dict = {"seed": None, "evaluate": None, "errors": []}

    def on_response(resp):
        try:
            url = resp.url
            if "/proposals/seed" in url and resp.request.method == "POST":
                api_hits["seed"] = {"status": resp.status, "body": resp.json() if resp.ok else resp.text()[:500]}
            if "/evaluate" in url and resp.request.method == "POST":
                api_hits["evaluate"] = {"status": resp.status, "body": resp.json() if resp.ok else resp.text()[:800]}
        except Exception as exc:  # noqa: BLE001
            api_hits["errors"].append(str(exc)[:200])

    page.on("response", on_response)
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
            """() => !document.querySelector('[data-testid=busy-popup]') &&
              !!(document.querySelector('[data-testid=find-opportunities],[data-testid=answer-input]'))""",
            timeout=90_000,
        )
    page.get_by_test_id("find-opportunities").click()
    page.get_by_test_id("opp-A").wait_for(timeout=180_000)
    page.get_by_test_id("opp-A").locator("button.btn").first.click()
    page.get_by_test_id("make-brief").click()
    page.get_by_test_id("brief-view").wait_for(timeout=180_000)
    page.get_by_test_id("to-compare").click()
    page.get_by_test_id("proposals").wait_for(timeout=60_000)
    if page.get_by_test_id("seed-proposals").count() and page.get_by_test_id("seed-proposals").is_visible():
        page.get_by_test_id("seed-proposals").click()
    # Seed handler also evaluates — wait for evaluation OR an error banner.
    page.wait_for_function(
        """() => {
          if (document.querySelector('[data-testid=evaluation-view]')) return true;
          if (document.querySelector('[data-testid=error], .notice.n-warn, [role=alert]')) {
            const t = document.body.innerText;
            if (/went wrong|try again|error|failed|quota|429/i.test(t) &&
                !document.querySelector('[data-testid=seed-proposals]')) return true;
          }
          return false;
        }""",
        timeout=420_000,
    )
    return api_hits


def extract(page) -> dict:
    return page.evaluate(
        """() => {
          const notice = document.querySelector('[data-testid=injection-notice]');
          const banner = document.querySelector('[data-testid=compare-banner-count]')?.textContent?.trim() || '';
          const summary = document.querySelector('[data-testid=rationale-summary]')?.textContent?.trim() || '';
          const rows = [...document.querySelectorAll('[data-testid=compare-desktop] tbody tr')].map((tr, i) => {
            const cells = [...tr.querySelectorAll('td')].map(td => td.innerText.replace(/\\s+/g, ' ').trim());
            const nameEl = tr.querySelector('[data-testid^=provider-name-]');
            return {
              rank: i + 1,
              id: nameEl?.getAttribute('data-testid')?.replace('provider-name-','') || '',
              name: nameEl?.textContent?.trim() || cells[1] || '',
              flagged: tr.getAttribute('data-flagged') === 'true' || /Flagged/i.test(tr.innerText),
              tech: cells[2], experience: cells[3], timeline: cells[4], cost: cells[5], risk: cells[6],
              overall: cells[7],
            };
          });
          return {
            banner, summary,
            notice: notice ? notice.textContent.trim() : null,
            flaggedName: notice?.getAttribute('data-flagged-name') || null,
            rows,
            cardCount: document.querySelectorAll('[data-testid^=compare-card-]').length,
            bodyHasEvaluation: !!document.querySelector('[data-testid=evaluation-view]'),
          };
        }"""
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        try:
            api_hits = drive_to_compare(page)
            data = extract(page)
            data["api"] = {
                "seed_status": (api_hits.get("seed") or {}).get("status"),
                "evaluate_status": (api_hits.get("evaluate") or {}).get("status"),
                "evaluate": (api_hits.get("evaluate") or {}).get("body"),
                "errors": api_hits.get("errors"),
            }
            # Prefer structured scores from evaluate API when present.
            ev = data["api"].get("evaluate")
            if isinstance(ev, dict) and "data" in ev:
                body = ev["data"]
                data["ranking"] = body.get("ranking")
                data["scores"] = [
                    {
                        "proposal_id": s["proposal_id"],
                        "overall_pct": round(s["overall"] * 100),
                        "criteria_pct": {k: round(v * 100) for k, v in s["criteria"].items()},
                    }
                    for s in body.get("scores", [])
                ]
                data["flags"] = body.get("flags")
                data["rationale"] = body.get("rationale", {}).get("summary")
            page.screenshot(path=str(OUT / "round3_compare_live_1280.png"), full_page=True)
            page.set_viewport_size({"width": 375, "height": 900})
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / "round3_compare_live_375.png"), full_page=True)
        except Exception as exc:
            page.screenshot(path=str(OUT / "round3_compare_live_fail.png"), full_page=True)
            data = {"error": str(exc), "snippet": page.inner_text("body")[:1500]}
            raise
        finally:
            (OUT / "round3_compare_live_scores.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            ctx.close()
            browser.close()
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
    print("Wrote", OUT / "round3_compare_live_scores.json")


if __name__ == "__main__":
    main()

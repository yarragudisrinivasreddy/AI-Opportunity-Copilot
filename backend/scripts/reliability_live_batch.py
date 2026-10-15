"""Run N live own-process cases against E2E_BASE_URL; append results JSONL.

Usage:
  set E2E_BASE_URL=https://y-srinivasreddy.web.app
  set REL_BATCH=5
  uv run python scripts/reliability_live_batch.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("E2E_BASE_URL", "https://y-srinivasreddy.web.app")
N = int(os.environ.get("REL_BATCH", "5"))
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "reliability_live.jsonl"
TEXTS = [
    "Operators check parts by eye, compare with a paper checklist, and write the result by hand. A supervisor reviews failed items at the end of each shift.",
    "Every morning trucks arrive with steel wire. Security writes the vehicle in a paper register. The store clerk matches the delivery challan to the purchase order by hand.",
    "Nurses write vitals on paper charts. At shift end someone types them into Excel. Missed readings are noticed the next morning.",
    "Warehouse staff pick orders from printed lists and tick boxes with a pen. Short picks are written on sticky notes for the supervisor.",
    "Clinic reception books appointments in a diary. Reminder calls are made from a handwritten list each evening.",
]


def one_case(page, text: str) -> dict:
    started = time.perf_counter()
    err = None
    stage = "home"
    try:
        page.goto(BASE, wait_until="networkidle")
        page.get_by_test_id("start-own").click()
        stage = "show"
        page.get_by_test_id("desc").fill(text)
        page.get_by_test_id("analyse").click()
        stage = "analyze"
        page.get_by_test_id("process-map").wait_for(timeout=180_000)
        page.get_by_test_id("confirm-map").click()
        stage = "questions"
        for ans in ["About 40 a day", "2 minutes", "Supervisor", "Some photos", "Excel"]:
            page.wait_for_function(
                """() => {
                  const find = document.querySelector('[data-testid=find-opportunities]');
                  if (find && find.offsetParent !== null) return true;
                  return !!document.querySelector('[data-testid=answer-input]');
                }""",
                timeout=120_000,
            )
            if page.get_by_test_id("find-opportunities").count() and page.get_by_test_id("find-opportunities").is_visible():
                break
            page.get_by_test_id("answer-input").fill(ans)
            page.get_by_test_id("answer").click()
            page.wait_for_function(
                "() => !document.querySelector('[data-testid=busy-popup]')",
                timeout=120_000,
            )
        page.get_by_test_id("find-opportunities").click()
        stage = "discover"
        page.get_by_test_id("discover").wait_for(timeout=180_000)
        page.locator("[data-testid^='select-opportunity-']").first.click()
        stage = "brief"
        page.get_by_test_id("brief-options").wait_for(timeout=30_000)
        page.get_by_test_id("make-brief").click()
        page.get_by_test_id("brief-view").wait_for(timeout=180_000)
        page.get_by_test_id("to-compare").click()
        stage = "evaluate"
        if page.get_by_test_id("seed-proposals").count() and page.get_by_test_id("seed-proposals").is_visible():
            page.get_by_test_id("seed-proposals").click()
        page.wait_for_function(
            """() => !!document.querySelector('[data-testid=evaluation-view]') ||
              !!(document.querySelector('[data-testid=evaluate]') &&
                 document.querySelector('[data-testid=evaluate]').offsetParent !== null)""",
            timeout=240_000,
        )
        if page.get_by_test_id("evaluate").count() and page.get_by_test_id("evaluate").is_visible():
            page.get_by_test_id("evaluate").click()
        page.get_by_test_id("evaluation-view").wait_for(timeout=240_000)
        ok = True
        stage = "done"
    except Exception as exc:  # noqa: BLE001
        ok = False
        err = f"{type(exc).__name__}: {exc}"[:400]
        # capture error banner if present
        try:
            if page.get_by_test_id("error-banner").count():
                err = (err or "") + " | " + page.get_by_test_id("error-banner").inner_text()[:200]
        except Exception:
            pass
    return {
        "ok": ok,
        "stage": stage,
        "error": err,
        "seconds": round(time.perf_counter() - started, 1),
        "at": datetime.now(timezone.utc).isoformat(),
        "run_id": str(uuid.uuid4())[:8],
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for i in range(N):
            page = browser.new_page()
            page.on("console", lambda m: None)
            r = one_case(page, TEXTS[i % len(TEXTS)])
            r["batch_index"] = i + 1
            r["base"] = BASE
            results.append(r)
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(json.dumps(r, ensure_ascii=False))
            page.close()
            time.sleep(8)  # breathe between cases (quota)
        browser.close()
    ok_n = sum(1 for r in results if r["ok"])
    print(json.dumps({"batch": N, "success": ok_n, "fail": N - ok_n, "log": str(OUT)}))
    return 0 if ok_n == N else 1


if __name__ == "__main__":
    raise SystemExit(main())

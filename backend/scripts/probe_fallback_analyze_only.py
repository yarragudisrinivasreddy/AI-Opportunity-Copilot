"""Analyze once on live Hosting while primary model is broken; report result + logs."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "fallback_probe.json"


def main() -> int:
    ok = False
    err = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://y-srinivasreddy.web.app", wait_until="networkidle")
            page.get_by_test_id("start-own").click()
            page.get_by_test_id("desc").fill(
                "Operators check parts by eye and write results on paper. "
                "A supervisor reviews failed items daily."
            )
            page.get_by_test_id("analyse").click()
            page.get_by_test_id("process-map").wait_for(timeout=240_000)
            ok = True
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"[:400]
            try:
                if page.get_by_test_id("error-banner").count():
                    err += " | " + page.get_by_test_id("error-banner").inner_text()[:200]
            except Exception:
                pass
        browser.close()

    logs = subprocess.run(
        "gcloud logging read "
        "\"resource.type=cloud_run_revision AND resource.labels.service_name=opportunity-copilot-api "
        "AND (textPayload:fallback OR textPayload:DOES-NOT-EXIST OR textPayload:gemini call)\" "
        "--project=y-srinivasreddy --limit=30 --format=value(textPayload)",
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = [ln for ln in (logs.stdout or "").splitlines() if ln.strip()][:20]
    report = {
        "analyze_ok": ok,
        "error": err,
        "log_lines": lines,
        "note": "Primary GEMINI_MODEL set to gemini-2.5-flash-DOES-NOT-EXIST-probe; fallback gemini-2.0-flash-001",
        "verdict": "PASS" if ok else "FAIL",
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:5000])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

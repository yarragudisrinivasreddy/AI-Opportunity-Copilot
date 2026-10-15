"""Temporarily point GEMINI_MODEL at a dead ID on Cloud Run; confirm fallback logs succeed.

Restores original env after the probe.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT = "y-srinivasreddy"
REGION = "us-central1"
SERVICE = "opportunity-copilot-api"
OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "fallback_probe.json"


def gcloud(*args: str) -> str:
    r = subprocess.run(
        ["gcloud", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout.strip()


def main() -> int:
    # Snapshot current env
    env_raw = gcloud(
        "run", "services", "describe", SERVICE,
        f"--region={REGION}", f"--project={PROJECT}",
        "--format=json(spec.template.spec.containers[0].env)",
    )
    envs = {e["name"]: e.get("value", "") for e in json.loads(env_raw)["spec"]["template"]["spec"]["containers"][0]["env"]}
    primary = envs.get("GEMINI_MODEL", "gemini-2.5-flash")
    fallback = envs.get("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash-001")
    report: dict = {"primary_before": primary, "fallback": fallback, "steps": []}

    # Force primary failure
    dead = "gemini-2.5-flash-DOES-NOT-EXIST-probe"
    gcloud(
        "run", "services", "update", SERVICE,
        f"--region={REGION}", f"--project={PROJECT}",
        f"--update-env-vars=GEMINI_MODEL={dead}",
        "--quiet",
    )
    report["steps"].append({"set_primary": dead})
    time.sleep(8)

    # Call analyze via a tiny Vertex-less path: hit health then rely on a browser case?
    # Prefer Cloud Logging after a smoke curl that triggers model — use playwright one analyze.
    from playwright.sync_api import sync_playwright

    ok = False
    err = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://y-srinivasreddy.web.app", wait_until="networkidle")
            page.get_by_test_id("start-own").click()
            page.get_by_test_id("desc").fill(
                "Operators check parts by eye and write results on paper. A supervisor reviews failed items daily."
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
    report["analyze_ok"] = ok
    report["analyze_error"] = err

    # Pull logs for fallback mention
    logs = gcloud(
        "logging", "read",
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" AND textPayload:"fallback"',
        f"--project={PROJECT}", "--limit=20", "--format=value(textPayload)",
    )
    report["fallback_log_lines"] = [ln for ln in logs.splitlines() if ln.strip()][:10]

    # Restore primary
    gcloud(
        "run", "services", "update", SERVICE,
        f"--region={REGION}", f"--project={PROJECT}",
        f"--update-env-vars=GEMINI_MODEL={primary}",
        "--quiet",
    )
    report["restored_primary"] = primary
    report["verdict"] = (
        "PASS" if ok and any("fallback" in ln.lower() for ln in report["fallback_log_lines"])
        else ("PASS_ANALYZE" if ok else "FAIL")
    )

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:4000])
    return 0 if report["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())

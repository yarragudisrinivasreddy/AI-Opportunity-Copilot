"""Lighthouse mobile on Home + Compare (sample path via debugging port)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff"
BASE = "https://y-srinivasreddy.web.app"
PORT = 9223


def scores(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: round(v["score"] * 100) for k, v in data.get("categories", {}).items()}


def run_lh(name: str) -> dict:
    path = OUT / f"lh_{name}_mobile.json"
    cmd = (
        f'npx --yes lighthouse "{BASE}" --port={PORT} '
        f"--only-categories=accessibility,best-practices,performance "
        f"--form-factor=mobile --output=json --output-path={path} --quiet"
    )
    subprocess.run(cmd, check=True, shell=True)
    return {"file": str(path.name), "scores": scores(path)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[f"--remote-debugging-port={PORT}", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(BASE, wait_until="networkidle")
        time.sleep(1)
        home = run_lh("home")
        page.get_by_test_id("try-sample").click()
        page.get_by_test_id("process-map").wait_for()
        page.get_by_test_id("confirm-map").click()
        page.get_by_test_id("questions").wait_for()
        for _ in range(3):
            page.get_by_test_id("question").locator("button.btn-quiet").first.click()
            page.wait_for_timeout(150)
        page.get_by_test_id("discover").wait_for()
        page.locator("[data-testid^='select-opportunity-']").first.click()
        page.get_by_test_id("brief-view").wait_for()
        page.get_by_test_id("to-compare").click()
        page.get_by_test_id("evaluation-view").wait_for()
        time.sleep(1)
        compare = run_lh("compare")
        browser.close()
    summary = {"home_mobile": home["scores"], "compare_mobile": compare["scores"]}
    (OUT / "lh_part_d_summary.json").write_text(
        json.dumps({"home": home, "compare": compare, "summary": summary}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    # Gate: a11y >= 90 preferred
    ok = all(summary["home_mobile"].get("accessibility", 0) >= 90 for _ in [0])
    ok = ok and summary["compare_mobile"].get("accessibility", 0) >= 90
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

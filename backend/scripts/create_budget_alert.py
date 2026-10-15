"""Create a Cloud Billing budget alert (~INR 2000 / ~USD 24) for the active billing account."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "billing_budget_alert.json"
PROJECT = "y-srinivasreddy"
# ~INR 2000 at ~84 INR/USD
AMOUNT_USD = 24


def main() -> int:
    # Resolve billing account linked to project
    r = subprocess.run(
        [
            "gcloud", "billing", "projects", "describe", PROJECT,
            "--format=json",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    info = json.loads(r.stdout or "{}") if r.returncode == 0 else {}
    acct = (info.get("billingAccountName") or "").replace("billingAccounts/", "")
    report = {"project": PROJECT, "billingAccount": acct, "amount_usd": AMOUNT_USD}

    if not acct:
        report["status"] = "FAIL"
        report["error"] = r.stderr or "no billing account on project"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    # Try gcloud billing budgets create (may need alpha/beta)
    display = "ai-opportunity-copilot-demo-cap"
    cmd = [
        "gcloud", "billing", "budgets", "create",
        f"--billing-account={acct}",
        f"--display-name={display}",
        f"--budget-amount={AMOUNT_USD}",
        f"--filter-projects=projects/{PROJECT}",
        "--threshold-rule=percent=50",
        "--threshold-rule=percent=90",
        "--threshold-rule=percent=100",
        "--format=json",
    ]
    created = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    report["create_stdout"] = (created.stdout or "")[:2000]
    report["create_stderr"] = (created.stderr or "")[:2000]
    report["create_exit"] = created.returncode
    if created.returncode != 0:
        # fallback: document console steps
        report["status"] = "MANUAL_REQUIRED"
        report["console"] = (
            f"https://console.cloud.google.com/billing/{acct}/budgets?project={PROJECT}"
        )
        report["instructions"] = (
            f"Create budget display-name={display}, amount USD {AMOUNT_USD} (~INR 2000), "
            "scope project y-srinivasreddy, thresholds 50/90/100% email alerts."
        )
    else:
        report["status"] = "CREATED"
        try:
            report["budget"] = json.loads(created.stdout)
        except json.JSONDecodeError:
            pass

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k not in ("create_stdout", "create_stderr")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

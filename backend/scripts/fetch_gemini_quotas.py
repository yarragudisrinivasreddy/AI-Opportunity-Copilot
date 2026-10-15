"""Fetch Gemini generate/image RPM quotas and write docs/visual_diff/quota_gemini.json."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "quota_gemini.json"
KEYS = (
    "generate_content_requests_per_minute_per_project_per_base_model",
    "generate_content_image_gen",
    "global_generate_content_requests_per_minute",
)


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from smoke_image import _print_access_token

    token = _print_access_token()
    import urllib.request

    url = (
        "https://serviceusage.googleapis.com/v1beta1/projects/y-srinivasreddy/"
        "services/aiplatform.googleapis.com/consumerQuotaMetrics?pageSize=200"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    metrics = data.get("metrics") or []
    out = []
    for m in metrics:
        met = m.get("metric", "")
        if not any(k in met for k in KEYS):
            continue
        row = {"display": m.get("displayName"), "metric": met, "limits": []}
        for lim in m.get("consumerQuotaLimits") or []:
            for b in lim.get("quotaBuckets") or []:
                row["limits"].append({
                    "unit": lim.get("unit"),
                    "effective": b.get("effectiveLimit"),
                    "default": b.get("defaultLimit"),
                    "dims": b.get("dimensions") or {},
                })
        out.append(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:5000])
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate 3 offline sample-case concept WebPs (Nano Banana), no people / no readable text."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Reuse smoke_image credential helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))
from smoke_image import _USD_PER_IMAGE_ESTIMATE, _credentials  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "frontend" / "public" / "img"
META_OUT = ROOT / "docs" / "visual_diff" / "sample_concept_images.json"

OPPS = [
    ("concept-opp-a", "AI visual pre-screening", "vision camera above a parts tray on an inspection table"),
    ("concept-opp-b", "Inspection copilot for operators", "tablet checklist beside measuring tools on a workbench"),
    ("concept-opp-c", "Automated result logging", "spreadsheet dashboard on a factory office desk with paper sheets nearby"),
]


def _to_webp(data: bytes, dest: Path, max_bytes: int = 250_000) -> tuple[int, str]:
    from app.llm.image import downscale_under

    out, mime = downscale_under(data, max_bytes)
    dest.write_bytes(out)
    return len(out), mime


def main() -> int:
    project = os.environ.get("GCP_PROJECT", "y-srinivasreddy").strip()
    location = (
        os.environ.get("GEMINI_IMAGE_LOCATION")
        or os.environ.get("GOOGLE_CLOUD_LOCATION")
        or "global"
    ).strip()
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1").strip()
    os.environ.setdefault("GCP_PROJECT", project)
    os.environ.setdefault("GEMINI_IMAGE_MODEL", model)
    os.environ.setdefault("GEMINI_IMAGE_LOCATION", location)

    creds = _credentials()
    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True, project=project, location=location, credentials=creds
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for kind, title, scene in OPPS:
        prompt = (
            f"flat editorial illustration of {scene}, "
            f"representing “{title}”, factory setting, "
            "no people, no faces, no readable text, no logos"
        )
        started = time.perf_counter()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        image_bytes: bytes | None = None
        for cand in getattr(response, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                if inline is not None and getattr(inline, "data", None):
                    data = inline.data
                    image_bytes = data if isinstance(data, (bytes, bytearray)) else bytes(data)
                    break
            if image_bytes:
                break
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if not image_bytes:
            print(f"FAIL {kind}: no image bytes after {elapsed_ms} ms")
            return 1
        dest = OUT_DIR / f"{kind}-800.webp"
        size, mime = _to_webp(image_bytes, dest)
        rec = {
            "kind": kind,
            "title": title,
            "prompt": prompt,
            "model": model,
            "location": location,
            "latency_ms": elapsed_ms,
            "bytes": size,
            "mime": mime,
            "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
            "cost_usd_estimate": _USD_PER_IMAGE_ESTIMATE,
            "caption": "AI-generated example illustration",
        }
        records.append(rec)
        print(f"OK {kind} bytes={size} ms={elapsed_ms} -> {dest.name}")

    META_OUT.write_text(
        __import__("json").dumps(
            {
                "model": model,
                "location": location,
                "usd_per_image_estimate": _USD_PER_IMAGE_ESTIMATE,
                "total_usd_estimate": round(_USD_PER_IMAGE_ESTIMATE * len(records), 4),
                "images": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Wrote", META_OUT)
    return 0


if __name__ == "__main__":
    # Ensure backend package import for downscale_under
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())

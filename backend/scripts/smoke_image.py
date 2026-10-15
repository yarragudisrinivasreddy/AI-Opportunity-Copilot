"""Smoke-test Vertex image generation for concept pictures (Nano Banana family).

  cd backend
  set GEMINI_IMAGE_MODEL=gemini-nano-banana-2.1
  set GEMINI_IMAGE_LOCATION=global
  set GCP_PROJECT=y-srinivasreddy
  python scripts/smoke_image.py

Model ID must come only from GEMINI_IMAGE_MODEL (no hard-coded Imagen IDs).
Uses google-genai generate_content with IMAGE modality.
Prefer: gcloud auth application-default login
Fallback: short-lived token from gcloud auth print-access-token.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# Agent Platform list price (Global, Standard PayGo): Image Output $30 / 1M tokens;
# 1K output = 1,120 tokens => $0.0336/image. Cite:
# https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing
_USD_PER_IMAGE_ESTIMATE = 0.0336


def _print_access_token() -> str:
    """Resolve a user access token via gcloud (Windows-safe)."""
    import shutil

    candidates: list[list[str]] = []
    for name in ("gcloud.cmd", "gcloud"):
        found = shutil.which(name)
        if found:
            candidates.append([found, "auth", "print-access-token"])
    for path in (
        r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
    ):
        if Path(path).is_file():
            candidates.append([path, "auth", "print-access-token"])
    # Direct python entry (avoids .ps1 wrapper issues under subprocess).
    gcloud_py = Path(r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py")
    if gcloud_py.is_file():
        candidates.append([sys.executable, str(gcloud_py), "auth", "print-access-token"])

    last_err: Exception | None = None
    for cmd in candidates:
        try:
            return subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE).strip()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    raise RuntimeError(f"gcloud auth print-access-token failed: {last_err}")


def _credentials():
    import google.auth
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials as UserCredentials

    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if creds and not getattr(creds, "valid", True) and hasattr(creds, "refresh"):
            creds.refresh(Request())
        if creds and (getattr(creds, "token", None) or getattr(creds, "valid", False)):
            print("ADC: google.auth.default() OK")
            return creds
    except Exception as exc:
        print(f"ADC default unavailable: {type(exc).__name__}: {exc}")

    try:
        token = _print_access_token()
    except Exception as exc:
        print(
            "FAIL: no Application Default Credentials. Run:\n"
            "  gcloud auth application-default login\n"
            f"(gcloud auth print-access-token also failed: {exc})"
        )
        raise SystemExit(2) from exc
    if not token:
        print("FAIL: empty gcloud token; run gcloud auth login && gcloud auth application-default login")
        raise SystemExit(2)
    print("ADC: using short-lived token from `gcloud auth print-access-token`")
    return UserCredentials(token=token)


def main() -> int:
    project = os.environ.get("GCP_PROJECT", "").strip()
    location = (
        os.environ.get("GEMINI_IMAGE_LOCATION")
        or os.environ.get("GOOGLE_CLOUD_LOCATION")
        or os.environ.get("GCP_LOCATION")
        or "global"
    ).strip()
    model = os.environ.get("GEMINI_IMAGE_MODEL", "").strip()

    print(f"GEMINI_IMAGE_MODEL={model or '(unset)'}")
    print(f"location={location or '(unset)'}")
    print(f"GCP_PROJECT={project or '(unset)'}")

    if not (project and location and model):
        print(
            "FAIL: set GCP_PROJECT, GEMINI_IMAGE_MODEL, and location "
            "(GEMINI_IMAGE_LOCATION preferred; try global)."
        )
        return 2

    creds = _credentials()
    prompt = (
        "flat editorial illustration of a tablet checklist on a factory workbench, "
        "factory setting, no people, no faces, no readable text, no logos"
    )

    started = time.perf_counter()
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            credentials=creds,
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
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
            print(f"FAIL: no image bytes returned after {elapsed_ms} ms")
            return 1

        out = Path(__file__).resolve().parents[2] / "docs" / "visual_diff" / "smoke_image_out.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(image_bytes)
        print(f"OK model={model}")
        print(f"location={location}")
        print(f"latency_ms={elapsed_ms}")
        print(f"bytes={len(image_bytes)}")
        print(f"cost_usd_estimate~={_USD_PER_IMAGE_ESTIMATE} (list-price guess; confirm in Model Garden)")
        print(f"wrote={out}")
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        print(f"FAIL after {elapsed_ms} ms: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

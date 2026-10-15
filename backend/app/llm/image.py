"""Concept-picture image clients. Never use FakeImageClient output in deck reports."""
from __future__ import annotations

import io
import logging
import os
from typing import Protocol

logger = logging.getLogger("app.llm.image")


class ImageClient(Protocol):
    def generate(self, prompt: str) -> bytes:
        """Return PNG/JPEG/WebP bytes for a sanitised concept prompt."""


class FakeImageClient:
    """Deterministic small PNG for tests. Do not report its output as a real visual."""

    def generate(self, prompt: str) -> bytes:
        try:
            from PIL import Image
        except ImportError:
            # Valid 1×1 RGB PNG (known-good IHDR/IDAT/IEND).
            return bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
                "0000000c4944415408d763f8cfc000000301010018dd8db40000000049454e44ae426082"
            )
        buf = io.BytesIO()
        Image.new("RGB", (64, 48), (40, 90, 120)).save(buf, format="PNG")
        return buf.getvalue()


class DisabledImageClient:
    def generate(self, prompt: str) -> bytes:
        raise RuntimeError("visuals disabled")


class VertexImageClient:
    """Nano Banana family via google-genai on Vertex. Model ID only from env/settings."""

    def __init__(self, project: str, location: str, model: str) -> None:
        if not (project and location and model):
            raise ValueError("project, location, and GEMINI_IMAGE_MODEL are required")
        self._project = project
        self._location = location
        self._model = model

    def generate(self, prompt: str) -> bytes:
        from google import genai
        from google.genai import types

        from app.llm.vertex import call_with_backoff

        client = genai.Client(
            vertexai=True,
            project=self._project,
            location=self._location,
        )
        response = call_with_backoff(
            lambda: client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
        )
        for cand in getattr(response, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                if inline is not None and getattr(inline, "data", None):
                    data = inline.data
                    return data if isinstance(data, (bytes, bytearray)) else bytes(data)
        raise RuntimeError("image model returned no image bytes")


def downscale_under(data: bytes, max_bytes: int = 250_000) -> tuple[bytes, str]:
    """Return (bytes, mime) as WebP/JPEG under max_bytes when Pillow is available."""
    try:
        from PIL import Image
    except ImportError:
        return data, "image/png"
    img = Image.open(io.BytesIO(data)).convert("RGB")
    quality = 85
    w, h = img.size
    for _ in range(8):
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=4)
        out = buf.getvalue()
        if len(out) <= max_bytes:
            return out, "image/webp"
        w, h = max(320, int(w * 0.75)), max(180, int(h * 0.75))
        img = img.resize((w, h))
        quality = max(55, quality - 8)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70, optimize=True)
    return buf.getvalue(), "image/jpeg"


def build_image_client(settings) -> ImageClient:
    if not settings.visuals_enabled:
        return DisabledImageClient()
    if settings.llm_mode != "vertex":
        return FakeImageClient()
    model = (settings.gemini_image_model or os.environ.get("GEMINI_IMAGE_MODEL", "")).strip()
    location = (
        os.environ.get("GEMINI_IMAGE_LOCATION")
        or settings.gcp_location
        or "global"
    ).strip()
    if not model:
        logger.warning("VISUALS_ENABLED but GEMINI_IMAGE_MODEL unset; using FakeImageClient")
        return FakeImageClient()
    return VertexImageClient(settings.gcp_project, location, model)

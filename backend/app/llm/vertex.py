"""Gemini on Vertex AI via the google-genai SDK.

The model ID is NEVER hard-coded; it comes from settings (GEMINI_MODEL).
Vertex rejects many JSON-Schema constraint keywords (minLength, maxItems, …) and
nullable anyOf/$ref shapes. We send a loosened schema to the API and keep full
Pydantic validation on the response (handoff / TASKS.md).
"""
import copy
import logging
import time
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.llm.client import ImagePart, LLMError, Part, T

logger = logging.getLogger("app.llm.vertex")

_STRIP_KEYS = frozenset({
    "minLength", "maxLength", "minItems", "maxItems",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "pattern", "default", "title", "description", "examples", "additionalProperties",
})


def vertex_response_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema Vertex accepts for response_schema (constraints validated in code)."""
    raw = model.model_json_schema()

    def strip(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if k in _STRIP_KEYS:
                    continue
                out[k] = strip(v)
            if "anyOf" in out:
                non_null = [x for x in out["anyOf"] if not (isinstance(x, dict) and x.get("type") == "null")]
                if len(non_null) == 1:
                    merged = dict(non_null[0]) if isinstance(non_null[0], dict) else {"type": "string"}
                    for k, v in out.items():
                        if k != "anyOf":
                            merged[k] = v
                    return strip(merged)
            return out
        if isinstance(obj, list):
            return [strip(x) for x in obj]
        return obj

    schema = strip(raw)
    defs = schema.pop("$defs", None) or schema.pop("definitions", None) or {}

    def inline(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                name = str(obj["$ref"]).split("/")[-1]
                return inline(copy.deepcopy(defs[name]))
            return {k: inline(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [inline(x) for x in obj]
        return obj

    return inline(schema)


class VertexGeminiClient:
    def __init__(self, project: str, location: str, model: str) -> None:
        if not (project and location and model):
            raise ValueError("GCP_PROJECT, GCP_LOCATION and GEMINI_MODEL must all be set")
        from google import genai  # lazy: keeps offline tests free of credentials

        # Explicit initialisation (project + location set in code, not implicit).
        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model

    def generate_structured(
        self,
        *,
        system: str,
        parts: Sequence[Part],
        schema: type[T],
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> T:
        from google.genai import types

        contents = [
            types.Part.from_bytes(data=p.data, mime_type=p.mime)
            if isinstance(p, ImagePart)
            else types.Part.from_text(text=p)
            for p in parts
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=vertex_response_schema(schema),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except Exception as exc:  # SDK raises several transport/API error types
            detail = str(exc).strip().replace("\n", " ")[:400]
            raise LLMError(f"model call failed: {type(exc).__name__}: {detail}") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        usage = getattr(response, "usage_metadata", None)
        logger.info(
            "gemini call schema=%s ms=%d in_tokens=%s out_tokens=%s",
            schema.__name__,
            elapsed_ms,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
        )
        text = getattr(response, "text", None)
        if not text:
            raise LLMError("empty model response")
        return schema.model_validate_json(text)

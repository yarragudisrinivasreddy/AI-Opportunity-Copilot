"""Gemini on Vertex AI via the google-genai SDK.

The model ID is NEVER hard-coded; it comes from settings (GEMINI_MODEL).
Optional GEMINI_FALLBACK_MODEL is tried only after primary retries are exhausted.
Vertex rejects many JSON-Schema constraint keywords (minLength, maxItems, …) and
nullable anyOf/$ref shapes. We send a loosened schema to the API and keep full
Pydantic validation on the response (see docs/ARCHITECTURE.md).
"""
import copy
import logging
import random
import re
import time
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel

from app.llm.client import ImagePart, LLMError, Part, T

logger = logging.getLogger("app.llm.vertex")

_R = TypeVar("_R")
# Transient Vertex / gateway errors worth backing off.
_RETRYABLE = re.compile(r"\b(429|503|RESOURCE_EXHAUSTED|UNAVAILABLE|Too Many Requests)\b", re.I)
# Primary-model missing / wrong ID — not worth retrying; fall through to GEMINI_FALLBACK_MODEL.
_FALLBACK_ELIGIBLE = re.compile(
    r"\b(429|503|RESOURCE_EXHAUSTED|UNAVAILABLE|Too Many Requests|404|NOT_FOUND|"
    r"Invalid Endpoint|Publisher model)\b",
    re.I,
)


def is_retryable_llm_error(exc: BaseException) -> bool:
    """True when the failure is a transient 429/503-class Vertex error."""
    text = f"{type(exc).__name__}: {exc}"
    return bool(_RETRYABLE.search(text))


def is_fallback_eligible_error(exc: BaseException) -> bool:
    """True when primary failure should try GEMINI_FALLBACK_MODEL (quota or missing model)."""
    text = f"{type(exc).__name__}: {exc}"
    return bool(_FALLBACK_ELIGIBLE.search(text))


def call_with_backoff(
    fn: Callable[[], _R],
    *,
    attempts: int = 3,
    base_delay_s: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> _R:
    """Run fn; on 429/503-class errors retry with jittered exponential backoff, then re-raise.

    Default max ~3 tries. Delay = base * 2^attempt * (0.5 + rng()) so jitter is 0.5×–1.5×.
    """
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classify then re-raise
            last = exc
            if not is_retryable_llm_error(exc) or attempt >= attempts - 1:
                raise
            jitter = 0.5 + float(rng())
            delay = base_delay_s * (2**attempt) * jitter
            logger.warning(
                "retryable LLM error attempt %d/%d; sleep %.2fs: %s",
                attempt + 1,
                attempts,
                delay,
                str(exc).replace("\n", " ")[:200],
            )
            sleep(delay)
    assert last is not None
    raise last


# JSON-Schema *keywords* Vertex rejects. Never strip these when they are
# property names under "properties" (e.g. a field called "title").
_STRIP_KEYS = frozenset({
    "minLength", "maxLength", "minItems", "maxItems",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "pattern", "default", "title", "description", "examples", "additionalProperties",
})


def vertex_response_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema Vertex accepts for response_schema (constraints validated in code)."""
    raw = model.model_json_schema()

    def strip(obj: Any, parent_key: str | None = None) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if parent_key != "properties" and k in _STRIP_KEYS:
                    continue
                out[k] = strip(v, k)
            if "anyOf" in out:
                non_null = [x for x in out["anyOf"] if not (isinstance(x, dict) and x.get("type") == "null")]
                if len(non_null) == 1:
                    merged = dict(non_null[0]) if isinstance(non_null[0], dict) else {"type": "string"}
                    for k, v in out.items():
                        if k != "anyOf":
                            merged[k] = v
                    return strip(merged, parent_key)
            return out
        if isinstance(obj, list):
            return [strip(x, parent_key) for x in obj]
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
    def __init__(
        self,
        project: str,
        location: str,
        model: str,
        fallback_model: str = "",
    ) -> None:
        if not (project and location and model):
            raise ValueError("GCP_PROJECT, GCP_LOCATION and GEMINI_MODEL must all be set")
        from google import genai  # lazy: keeps offline tests free of credentials

        # Explicit initialisation (project + location set in code, not implicit).
        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model
        self._fallback = (fallback_model or "").strip()
        if self._fallback == self._model:
            self._fallback = ""

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

        def _call(model_id: str):
            return call_with_backoff(
                lambda: self._client.models.generate_content(
                    model=model_id, contents=contents, config=config
                ),
                attempts=3,
            )

        started = time.perf_counter()
        used_model = self._model
        try:
            response = _call(self._model)
        except Exception as exc:  # SDK raises several transport/API error types
            if self._fallback and is_fallback_eligible_error(exc):
                logger.warning(
                    "primary model %s failed after retries (%s); trying fallback %s",
                    self._model,
                    type(exc).__name__,
                    self._fallback,
                )
                used_model = self._fallback
                try:
                    response = _call(self._fallback)
                except Exception as fb_exc:  # noqa: BLE001
                    detail = str(fb_exc).strip().replace("\n", " ")[:400]
                    raise LLMError(f"model call failed: {type(fb_exc).__name__}: {detail}") from fb_exc
            else:
                detail = str(exc).strip().replace("\n", " ")[:400]
                raise LLMError(f"model call failed: {type(exc).__name__}: {detail}") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        usage = getattr(response, "usage_metadata", None)
        logger.info(
            "gemini call model=%s schema=%s ms=%d in_tokens=%s out_tokens=%s",
            used_model,
            schema.__name__,
            elapsed_ms,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
        )
        text = getattr(response, "text", None)
        if not text:
            raise LLMError("empty model response")
        return schema.model_validate_json(text)

"""Jittered exponential backoff on Vertex 429/503-class errors + fallback model."""
from __future__ import annotations

import pytest

from app.llm.vertex import VertexGeminiClient, call_with_backoff, is_retryable_llm_error


def test_is_retryable_detects_429_and_503():
    assert is_retryable_llm_error(RuntimeError("ClientError: 429 RESOURCE_EXHAUSTED"))
    assert is_retryable_llm_error(RuntimeError("503 UNAVAILABLE"))
    assert is_retryable_llm_error(RuntimeError("Too Many Requests"))
    assert not is_retryable_llm_error(RuntimeError("400 INVALID_ARGUMENT"))
    assert not is_retryable_llm_error(ValueError("empty model response"))


def test_call_with_backoff_retries_then_succeeds():
    sleeps: list[float] = []
    n = {"i": 0}

    def flaky():
        n["i"] += 1
        if n["i"] < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return "ok"

    # rng → 0.5 so jitter factor is exactly 1.0
    assert (
        call_with_backoff(
            flaky, attempts=3, base_delay_s=0.25, sleep=sleeps.append, rng=lambda: 0.5
        )
        == "ok"
    )
    assert n["i"] == 3
    assert sleeps == [0.25, 0.5]


def test_call_with_backoff_gives_up_after_attempts():
    sleeps: list[float] = []

    def always():
        raise RuntimeError("503 UNAVAILABLE")

    with pytest.raises(RuntimeError, match="503"):
        call_with_backoff(
            always, attempts=3, base_delay_s=0.1, sleep=sleeps.append, rng=lambda: 0.5
        )
    assert sleeps == [0.1, 0.2]


def test_call_with_backoff_applies_jitter():
    sleeps: list[float] = []

    def always():
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    with pytest.raises(RuntimeError):
        call_with_backoff(
            always, attempts=2, base_delay_s=1.0, sleep=sleeps.append, rng=lambda: 1.0
        )
    # factor = 0.5 + 1.0 = 1.5 → delay 1.5
    assert sleeps == pytest.approx([1.5])


def test_non_retryable_raises_immediately():
    sleeps: list[float] = []
    n = {"i": 0}

    def bad():
        n["i"] += 1
        raise RuntimeError("400 INVALID_ARGUMENT")

    with pytest.raises(RuntimeError, match="400"):
        call_with_backoff(bad, attempts=3, base_delay_s=1.0, sleep=sleeps.append)
    assert n["i"] == 1 and sleeps == []


def test_fallback_model_used_after_primary_retries(monkeypatch):
    """GEMINI_FALLBACK_MODEL is only used after primary retries fail on 429/503."""
    from pydantic import BaseModel

    class Tiny(BaseModel):
        x: int

    calls: list[str] = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):  # noqa: ARG002
            calls.append(model)
            if model == "primary-model":
                raise RuntimeError("429 RESOURCE_EXHAUSTED")

            class R:
                text = '{"x": 1}'
                usage_metadata = None

            return R()

    class FakeClient:
        def __init__(self, *a, **k):  # noqa: ARG002
            self.models = FakeModels()

    monkeypatch.setattr("google.genai.Client", FakeClient)
    # Skip real backoff sleeps during the unit test.
    monkeypatch.setattr(
        "app.llm.vertex.call_with_backoff",
        lambda fn, **kw: fn(),  # noqa: ARG005
    )

    client = VertexGeminiClient("proj", "us-central1", "primary-model", fallback_model="fallback-model")
    out = client.generate_structured(system="s", parts=["hi"], schema=Tiny)
    assert out.x == 1
    assert calls == ["primary-model", "fallback-model"]

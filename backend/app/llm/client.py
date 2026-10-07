"""LLM abstraction. Agents depend on this Protocol, never on a vendor SDK directly."""
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("app.llm")
T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ImagePart:
    data: bytes
    mime: str = "image/jpeg"


Part = str | ImagePart


class LLMError(Exception):
    """Model call failed or returned unusable output."""


class LLMClient(Protocol):
    def generate_structured(
        self,
        *,
        system: str,
        parts: Sequence[Part],
        schema: type[T],
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> T: ...


def structured_call(
    client: LLMClient,
    *,
    system: str,
    parts: Sequence[Part],
    schema: type[T],
    validator: Callable[[T], list[str]] | None = None,
    retries: int = 1,
    strict: bool = True,
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
) -> T:
    """Call the model, validate against the schema and an optional semantic validator.

    On failure, retry (default once) with the problems appended. Raises LLMError when all
    attempts fail, so callers can fall back safely. With strict=False, a schema-valid result
    that still fails the semantic validator is returned after the retries so the caller can
    repair it conservatively (for example, downgrading ungrounded observations).
    """
    last_result: BaseModel | None = None
    attempt_parts = list(parts)
    last_problem = "unknown"
    for attempt in range(retries + 1):
        try:
            result = client.generate_structured(
                system=system,
                parts=attempt_parts,
                schema=schema,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        except (LLMError, ValidationError) as exc:
            last_problem = f"{type(exc).__name__}: {str(exc)[:200]}"
            logger.warning("structured_call attempt %d failed: %s", attempt + 1, last_problem)
            continue
        problems = validator(result) if validator else []
        if not problems:
            return result
        last_result = result
        last_problem = "; ".join(problems)[:400]
        logger.warning("structured_call attempt %d invalid: %s", attempt + 1, last_problem)
        attempt_parts = list(parts) + [
            "Your previous output had these problems. Fix them and answer again: " + last_problem
        ]
    if not strict and last_result is not None:
        return last_result  # type: ignore[return-value]
    raise LLMError(f"model output unusable after {retries + 1} attempt(s): {last_problem}")

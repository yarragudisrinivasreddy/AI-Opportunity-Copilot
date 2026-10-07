"""Agent 1: reconstruct the process from sanitised frames and/or a description."""
import logging

from app.core import injection, text_pii
from app.llm import prompts
from app.llm.client import ImagePart, LLMClient, Part, structured_call
from app.schemas.process import Process, downgrade_ungrounded, ungrounded_observations

logger = logging.getLogger("app.agents.vision")


def frame_id(index: int) -> str:
    return f"frame_{index}"


def clean_user_text(text: str | None) -> tuple[str, int]:
    """Redact obvious PII and strip instruction-like segments from user free text."""
    if not text:
        return "", 0
    redacted = text_pii.redact_text(text).text
    report = injection.scan(redacted)
    return report.sanitized_text, report.removed_segments


class VisionProcessAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def analyze(self, frames: list[bytes], description: str | None) -> Process:
        if not frames and not (description and description.strip()):
            raise ValueError("provide at least one image/frame or a description")
        allowed = {frame_id(i) for i in range(len(frames))}
        if description:
            allowed.add("description")

        parts: list[Part] = []
        for i, data in enumerate(frames):
            parts.append(f"{frame_id(i)}:")
            parts.append(ImagePart(data=data, mime="image/jpeg"))
        text, _removed = clean_user_text(description)
        if text:
            parts.append(prompts.wrap_untrusted("user_description", text))
        parts.append("Reconstruct the process now.")

        def validate(p: Process) -> list[str]:
            problems: list[str] = []
            for step in p.steps:
                if step.kind == "observation" and step.evidence_ref not in allowed:
                    problems.append(
                        f"step {step.id}: observation needs evidence_ref in {sorted(allowed)}"
                    )
            if len({s.id for s in p.steps}) != len(p.steps):
                problems.append("step ids must be unique")
            return problems

        process = structured_call(
            self._llm,
            system=prompts.PROCESS_SYSTEM,
            parts=parts,
            schema=Process,
            validator=validate,
            strict=False,
            temperature=0.1,
        )
        # Conservative fallback if something still slipped through: demote to assumption.
        for step in process.steps:
            if step.evidence_ref and step.evidence_ref not in allowed:
                step.evidence_ref = None
        if ungrounded_observations(process):
            logger.warning("downgrading ungrounded observations to assumptions")
            process = downgrade_ungrounded(process)
        return process

"""Process understanding schemas (Agent 1 output). See docs/AGENT_SPEC.md."""
from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal["observation", "assumption"]

# Facts the rubric and brief need. Agent 1 reports which are still missing.
MissingField = Literal[
    "volume", "time_per_unit", "exception_handling", "data_availability", "systems_used"
]


class ProcessStep(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=500)
    kind: Kind
    evidence_ref: str | None = None
    manual: bool = True
    decision_point: bool = False
    data_entry: bool = False


class PainPoint(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    kind: Kind
    evidence_ref: str | None = None


class Process(BaseModel):
    process_name: str = Field(min_length=1, max_length=200)
    environment: str = Field(default="", max_length=300)
    actors: list[str] = Field(default_factory=list, max_length=10)
    tools: list[str] = Field(default_factory=list, max_length=15)
    steps: list[ProcessStep] = Field(min_length=1, max_length=25)
    pain_points: list[PainPoint] = Field(default_factory=list, max_length=10)
    missing_fields: list[MissingField] = Field(default_factory=list)


def ungrounded_observations(process: Process) -> list[str]:
    """Ids of steps/pain points labelled observation without an evidence reference."""
    bad = [s.id for s in process.steps if s.kind == "observation" and not s.evidence_ref]
    bad += [
        f"pain:{i}"
        for i, p in enumerate(process.pain_points)
        if p.kind == "observation" and not p.evidence_ref
    ]
    return bad


def downgrade_ungrounded(process: Process) -> Process:
    """Conservative fallback: relabel ungrounded observations as assumptions."""
    data = process.model_copy(deep=True)
    for step in data.steps:
        if step.kind == "observation" and not step.evidence_ref:
            step.kind = "assumption"
    for pain in data.pain_points:
        if pain.kind == "observation" and not pain.evidence_ref:
            pain.kind = "assumption"
    return data

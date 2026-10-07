"""Opportunity and rubric schemas (Agent 2 output). Enums only; no LLM-invented scores."""
from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["low", "medium", "high"]
DataLevel = Literal["low", "medium", "high", "unknown"]


class Rubric(BaseModel):
    repetitive_work: Level
    data_availability: DataLevel
    ai_feasibility: Level
    business_impact: Level
    implementation_complexity: Level
    human_oversight_required: bool
    # True when a simple rule-based workflow would likely be enough.
    rule_based_sufficient: bool = False


class OpportunityDraft(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=800)
    rubric: Rubric
    evidence_refs: list[str] = Field(default_factory=list, max_length=10)


class OpportunitySet(BaseModel):
    opportunities: list[OpportunityDraft] = Field(default_factory=list, max_length=3)
    # Required when the list is empty: why AI is not the right tool.
    not_ai_explanation: str | None = Field(default=None, max_length=800)


class Opportunity(OpportunityDraft):
    id: str
    strength: int
    recommendation: str
    flags: list[str] = Field(default_factory=list)
    selected: bool = False

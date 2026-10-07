"""Build brief schema (Agent 3 output). See PRD section 12."""
from pydantic import BaseModel, Field

BRIEF_STATUS = "proposal_only"
BRIEF_DISCLAIMER = (
    "This brief describes a proposed AI solution. No part of it has been built or "
    "validated by this product. Estimates are ranges based on stated assumptions."
)


class ApproachItem(BaseModel):
    approach: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=300)


class ExpectedOutcome(BaseModel):
    metric: str = Field(min_length=1, max_length=200)
    low: float
    high: float
    unit: str = Field(max_length=40)
    assumption: str = Field(min_length=1, max_length=400)


class BriefRisk(BaseModel):
    risk: str = Field(min_length=1, max_length=300)
    mitigation_prompt: str = Field(min_length=1, max_length=300)


class Phase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=400)
    exit_criteria: str = Field(min_length=1, max_length=300)


class BriefDraft(BaseModel):
    problem: str = Field(min_length=1, max_length=1200)
    current_workflow: list[str] = Field(min_length=1, max_length=25)
    proposed_solution: str = Field(min_length=1, max_length=1200)
    ai_approaches: list[ApproachItem] = Field(min_length=1, max_length=8)
    required_data: list[str] = Field(min_length=1, max_length=12)
    integrations: list[str] = Field(default_factory=list, max_length=12)
    human_in_the_loop: list[str] = Field(min_length=1, max_length=10)
    expected_outcomes: list[ExpectedOutcome] = Field(default_factory=list, max_length=8)
    risks: list[BriefRisk] = Field(min_length=1, max_length=10)
    phases: list[Phase] = Field(min_length=3, max_length=3)
    assumptions: list[str] = Field(min_length=1, max_length=20)
    proposal_requirements: list[str] = Field(min_length=1, max_length=15)


class Brief(BriefDraft):
    """Brief as stored/served: code adds the fixed status and disclaimer."""

    status: str = BRIEF_STATUS
    disclaimer: str = BRIEF_DISCLAIMER
    opportunity_id: str
    # Provider-facing fields come from the user (or are flagged as inferred).
    target_timeline_weeks: float | None = None
    budget_low_inr: float | None = None
    budget_high_inr: float | None = None

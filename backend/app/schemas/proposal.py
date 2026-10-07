"""Proposal, extraction and evaluation schemas. See PRD sections 13-14."""
from typing import Literal

from pydantic import BaseModel, Field


class SimilarProject(BaseModel):
    vertical: str = Field(max_length=100)
    problem_type: str = Field(max_length=150)
    outcome: str = Field(max_length=300)


class ProposalRisk(BaseModel):
    risk: str = Field(max_length=300)
    mitigation: str | None = Field(default=None, max_length=300)


class RequirementResponse(BaseModel):
    requirement_id: str = Field(max_length=20)
    response: str = Field(max_length=1200)


class Proposal(BaseModel):
    provider_id: str
    solution_approach: str = Field(max_length=2000)
    architecture: str = Field(max_length=2000)
    technologies: list[str] = Field(default_factory=list, max_length=20)
    timeline_weeks: float | None = None
    cost_inr: float | None = None
    team: str = Field(default="", max_length=500)
    similar_projects: list[SimilarProject] = Field(default_factory=list, max_length=10)
    risks: list[ProposalRisk] = Field(default_factory=list, max_length=12)
    support: str = Field(default="", max_length=500)
    expected_outcomes: list[str] = Field(default_factory=list, max_length=10)
    requirement_responses: list[RequirementResponse] = Field(default_factory=list, max_length=20)


class Provider(BaseModel):
    id: str
    name: str
    capabilities: list[str]
    industries: list[str]
    typical_range_inr_min: float
    typical_range_inr_max: float
    simulated: bool = True


# ---- Stage 1: extractor output (no scoring authority) ----
class RequirementCoverage(BaseModel):
    requirement_id: str
    status: Literal["covered", "partial", "not_covered"]
    field_path: str = ""


class ProjectRelevance(BaseModel):
    relevance: Literal["same_vertical_and_problem", "adjacent", "unrelated"]
    field_path: str = ""


class RiskMitigation(BaseModel):
    mitigated: bool
    field_path: str = ""


class ExtractedProposalDraft(BaseModel):
    requirement_coverage: list[RequirementCoverage] = Field(default_factory=list, max_length=30)
    similar_projects: list[ProjectRelevance] = Field(default_factory=list, max_length=10)
    timeline_weeks: float | None = None
    cost_inr: float | None = None
    risks: list[RiskMitigation] = Field(default_factory=list, max_length=15)
    human_in_loop_addressed: bool = False
    data_readiness_plan: bool = False
    model_detected_injection: bool = False


class InjectionFlag(BaseModel):
    detected: bool = False
    reasons: list[str] = Field(default_factory=list)
    removed_segments: int = 0


class ExtractedProposal(ExtractedProposalDraft):
    proposal_id: str
    injection_flag: InjectionFlag = Field(default_factory=InjectionFlag)


# ---- Stage 2: scorer output ----
CRITERIA = ("technical_fit", "experience", "timeline", "cost", "risk")


class Weights(BaseModel):
    technical_fit: float = 0.35
    experience: float = 0.20
    timeline: float = 0.15
    cost: float = 0.15
    risk: float = 0.15


class ProposalScore(BaseModel):
    proposal_id: str
    criteria: dict[str, float]
    overall: float


# ---- Stage 3: rationale ----
class RationalePoint(BaseModel):
    proposal_id: str
    criterion: str
    score: float
    field_path: str = ""


class RationaleDraft(BaseModel):
    recommended_proposal_id: str
    summary: str = Field(max_length=1500)
    points: list[RationalePoint] = Field(default_factory=list, max_length=20)


class Evaluation(BaseModel):
    brief_id: str
    weights: Weights
    flags: list[str] = Field(default_factory=list)
    extracted: list[ExtractedProposal]
    scores: list[ProposalScore]
    ranking: list[str]
    rationale: RationaleDraft
    rationale_validated: bool
    rationale_source: Literal["model", "template"]

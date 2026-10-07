"""Deterministic recommendation from rubric enums (PRD section 11). Pure code, unit-tested."""
from app.schemas.opportunity import Rubric

_POINTS = {"low": 1, "medium": 2, "high": 3, "unknown": 1}
_INVERTED = {"low": 3, "medium": 2, "high": 1}

REC_STRONG = "Strong candidate for AI exploration"
REC_CANDIDATE = "Candidate: validate with a small proof of concept"
REC_WEAK = "Not a strong AI candidate"
REC_RULE_BASED = "Consider a simple rule-based workflow first"
FLAG_DATA = "Confirm data availability before committing"

# Initial thresholds. Tune on the benchmark and record changes in docs/PRD.md.
WEAK_MAX = 7
CANDIDATE_MAX = 10


def strength(rubric: Rubric) -> int:
    """Sum of five factors, range 5..15 (complexity is inverted)."""
    return (
        _POINTS[rubric.repetitive_work]
        + _POINTS[rubric.ai_feasibility]
        + _POINTS[rubric.business_impact]
        + _POINTS[rubric.data_availability]
        + _INVERTED[rubric.implementation_complexity]
    )


def recommend(rubric: Rubric) -> tuple[int, str, list[str]]:
    """Return (strength, recommendation, flags). Same input always gives same output."""
    score = strength(rubric)
    if rubric.ai_feasibility == "low" or score <= WEAK_MAX:
        rec = REC_WEAK
    elif score <= CANDIDATE_MAX:
        rec = REC_CANDIDATE
    else:
        rec = REC_STRONG

    flags: list[str] = []
    if rubric.data_availability in ("low", "unknown"):
        flags.append(FLAG_DATA)
    if rubric.human_oversight_required:
        flags.append("Human oversight required")
    if rubric.rule_based_sufficient:
        rec = REC_RULE_BASED
    return score, rec, flags

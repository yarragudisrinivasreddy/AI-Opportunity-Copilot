"""Stage 2: deterministic bid scorer (PRD section 14). Code decides; the LLM never scores."""
from dataclasses import dataclass
from statistics import median

from app.schemas.proposal import CRITERIA, ExtractedProposal, ProposalScore, Weights


@dataclass(frozen=True)
class ScoringContext:
    target_weeks: float
    budget_low: float
    budget_high: float
    flags: tuple[str, ...] = ()


def validate_weights(weights: Weights) -> Weights:
    values = [getattr(weights, c) for c in CRITERIA]
    if any(v < 0 for v in values):
        raise ValueError("weights must be non-negative")
    total = sum(values)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    if abs(total - 1.0) < 1e-9:
        return weights
    return Weights(**{c: getattr(weights, c) / total for c in CRITERIA})


def build_context(
    target_weeks: float | None,
    budget_low: float | None,
    budget_high: float | None,
    extracted: list[ExtractedProposal],
) -> ScoringContext:
    """Use user-supplied targets; otherwise infer from the proposals and FLAG it."""
    flags: list[str] = []
    weeks = [e.timeline_weeks for e in extracted if e.timeline_weeks]
    costs = [e.cost_inr for e in extracted if e.cost_inr]
    if not target_weeks:
        target_weeks = min(weeks) if weeks else 1.0
        flags.append("target_timeline_inferred")
    if not budget_low or not budget_high:
        budget_low = min(costs) if costs else 1.0
        budget_high = max(costs) if costs else 1.0
        flags.append("budget_inferred")
    return ScoringContext(float(target_weeks), float(budget_low), float(budget_high), tuple(flags))


def _linear_down(value: float | None, full_until: float, zero_at: float) -> float:
    if value is None or value <= 0:
        return 0.0
    if value <= full_until:
        return 1.0
    if value >= zero_at or zero_at <= full_until:
        return 0.0
    return round(1.0 - (value - full_until) / (zero_at - full_until), 6)


def technical_fit(e: ExtractedProposal) -> float:
    total = len(e.requirement_coverage)
    if total == 0:
        return 0.0
    covered = sum(1 for r in e.requirement_coverage if r.status == "covered")
    partial = sum(1 for r in e.requirement_coverage if r.status == "partial")
    return (covered + 0.5 * partial) / total


def experience(e: ExtractedProposal) -> float:
    same = sum(1 for p in e.similar_projects if p.relevance == "same_vertical_and_problem")
    adjacent = sum(1 for p in e.similar_projects if p.relevance == "adjacent")
    return min(1.0, (2 * same + adjacent) / 4.0)


def timeline(e: ExtractedProposal, ctx: ScoringContext) -> float:
    return _linear_down(e.timeline_weeks, ctx.target_weeks, 2 * ctx.target_weeks)


def cost(e: ExtractedProposal, ctx: ScoringContext) -> float:
    return _linear_down(e.cost_inr, ctx.budget_low, 1.5 * ctx.budget_high)


def risk(e: ExtractedProposal) -> float:
    total = len(e.risks)
    # Acknowledging no risks at all is a negative signal, so it earns no mitigation credit.
    mitigated_share = (sum(1 for r in e.risks if r.mitigated) / total) if total else 0.0
    return 0.5 * mitigated_share + 0.25 * float(e.human_in_loop_addressed) + 0.25 * float(
        e.data_readiness_plan
    )


def score_all(
    extracted: list[ExtractedProposal], weights: Weights, ctx: ScoringContext
) -> list[ProposalScore]:
    weights = validate_weights(weights)
    results: list[ProposalScore] = []
    for e in extracted:
        criteria = {
            "technical_fit": technical_fit(e),
            "experience": experience(e),
            "timeline": timeline(e, ctx),
            "cost": cost(e, ctx),
            "risk": risk(e),
        }
        criteria = {k: round(v, 4) for k, v in criteria.items()}
        overall = round(sum(getattr(weights, c) * criteria[c] for c in CRITERIA), 4)
        results.append(ProposalScore(proposal_id=e.proposal_id, criteria=criteria, overall=overall))
    return results


def rank(scores: list[ProposalScore], costs: dict[str, float | None]) -> list[str]:
    """Higher overall first; ties broken by technical fit, then lower cost, then id."""

    def key(s: ProposalScore) -> tuple:
        c = costs.get(s.proposal_id)
        return (-s.overall, -s.criteria["technical_fit"], c if c else float("inf"), s.proposal_id)

    return [s.proposal_id for s in sorted(scores, key=key)]


def median_or_none(values: list[float]) -> float | None:
    return median(values) if values else None

import pytest

from app.core import scoring
from app.core.paths import resolve
from app.schemas.proposal import (ExtractedProposal, ProjectRelevance, RequirementCoverage,
                                  RiskMitigation, Weights)


def ex(pid="p", cov=("covered",) * 4, proj=("same_vertical_and_problem",), weeks=10, cost=900000,
       risks=(True, True), hil=True, data=True):
    return ExtractedProposal(
        proposal_id=pid,
        requirement_coverage=[RequirementCoverage(requirement_id=f"R{i}", status=s) for i, s in enumerate(cov, 1)],
        similar_projects=[ProjectRelevance(relevance=p) for p in proj],
        timeline_weeks=weeks, cost_inr=cost,
        risks=[RiskMitigation(mitigated=m) for m in risks],
        human_in_loop_addressed=hil, data_readiness_plan=data,
    )


CTX = scoring.ScoringContext(target_weeks=12, budget_low=800000, budget_high=1200000)


def test_technical_fit():
    assert scoring.technical_fit(ex(cov=("covered", "partial", "not_covered", "covered"))) == pytest.approx(2.5 / 4)
    assert scoring.technical_fit(ex(cov=())) == 0.0


def test_experience_caps_at_one():
    assert scoring.experience(ex(proj=("same_vertical_and_problem",) * 3)) == 1.0
    assert scoring.experience(ex(proj=("adjacent",))) == 0.25
    assert scoring.experience(ex(proj=())) == 0.0


def test_timeline_linear():
    assert scoring.timeline(ex(weeks=12), CTX) == 1.0
    assert scoring.timeline(ex(weeks=18), CTX) == pytest.approx(0.5)
    assert scoring.timeline(ex(weeks=24), CTX) == 0.0
    assert scoring.timeline(ex(weeks=None), CTX) == 0.0


def test_cost_linear():
    assert scoring.cost(ex(cost=800000), CTX) == 1.0
    assert scoring.cost(ex(cost=1800000), CTX) == 0.0
    mid = scoring.cost(ex(cost=1300000), CTX)
    assert 0 < mid < 1


def test_risk_components():
    assert scoring.risk(ex(risks=(True, True), hil=True, data=True)) == 1.0
    assert scoring.risk(ex(risks=(), hil=True, data=True)) == 0.5  # no risks named earns no mitigation credit
    assert scoring.risk(ex(risks=(True, False), hil=False, data=False)) == 0.25


def test_weights_normalise_and_reject():
    w = scoring.validate_weights(Weights(technical_fit=2, experience=1, timeline=1, cost=1, risk=1))
    assert sum([w.technical_fit, w.experience, w.timeline, w.cost, w.risk]) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        scoring.validate_weights(Weights(technical_fit=-1))
    with pytest.raises(ValueError):
        scoring.validate_weights(Weights(technical_fit=0, experience=0, timeline=0, cost=0, risk=0))


def test_overall_and_ranking_tiebreak():
    a, b = ex("a"), ex("b", cost=950000)
    scores = scoring.score_all([a, b], Weights(), CTX)
    ranking = scoring.rank(scores, {"a": a.cost_inr, "b": b.cost_inr})
    assert ranking[0] == "a"  # a is cheaper -> higher cost score
    c, d = ex("c"), ex("d")
    scores = scoring.score_all([c, d], Weights(), CTX)
    assert scoring.rank(scores, {"c": 900000, "d": 900000}) == ["c", "d"]  # id tiebreak is stable


def test_context_inference_is_flagged():
    ctx = scoring.build_context(None, None, None, [ex("a", weeks=10, cost=700000), ex("b", weeks=14, cost=900000)])
    assert set(ctx.flags) == {"target_timeline_inferred", "budget_inferred"}
    assert ctx.target_weeks == 10 and ctx.budget_low == 700000 and ctx.budget_high == 900000
    given = scoring.build_context(12, 800000, 1200000, [ex()])
    assert given.flags == ()


def test_scores_deterministic():
    one = scoring.score_all([ex("a"), ex("b", weeks=20)], Weights(), CTX)
    two = scoring.score_all([ex("a"), ex("b", weeks=20)], Weights(), CTX)
    assert one == two


def test_paths():
    data = {"risks": [{"mitigated": True}], "timeline_weeks": None}
    assert resolve(data, "risks[0].mitigated") == (True, True)
    assert resolve(data, "timeline_weeks") == (True, None)
    assert resolve(data, "risks[1]")[0] is False
    assert resolve(data, "nope")[0] is False
    assert resolve(data, "")[0] is False

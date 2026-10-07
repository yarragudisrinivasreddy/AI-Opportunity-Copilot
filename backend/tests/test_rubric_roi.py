import pytest

from app.core import rubric as r
from app.core import roi
from app.schemas.opportunity import Rubric


def rub(**kw):
    base = dict(repetitive_work="high", data_availability="high", ai_feasibility="high",
                business_impact="high", implementation_complexity="low", human_oversight_required=True)
    base.update(kw)
    return Rubric(**base)


def test_strength_range_and_strong_candidate():
    s, rec, flags = r.recommend(rub())
    assert s == 15 and rec == r.REC_STRONG
    assert "Human oversight required" in flags


def test_weak_when_feasibility_low_even_if_strength_high():
    _, rec, _ = r.recommend(rub(ai_feasibility="low"))
    assert rec == r.REC_WEAK


def test_threshold_boundaries():
    # strength 7 -> weak, 8 -> candidate, 10 -> candidate, 11 -> strong
    cases = [
        (rub(repetitive_work="low", data_availability="low", ai_feasibility="medium", business_impact="low", implementation_complexity="high"), 6, r.REC_WEAK),
        (rub(repetitive_work="medium", data_availability="low", ai_feasibility="medium", business_impact="medium", implementation_complexity="high"), 8, r.REC_CANDIDATE),
        (rub(repetitive_work="high", data_availability="medium", ai_feasibility="medium", business_impact="medium", implementation_complexity="medium"), 11, r.REC_STRONG),
    ]
    for rubric, expected_strength, expected in cases:
        s, rec, _ = r.recommend(rubric)
        assert s == expected_strength and rec == expected


def test_unknown_data_scores_low_and_flags():
    s_unknown, _, flags = r.recommend(rub(data_availability="unknown"))
    s_low, _, _ = r.recommend(rub(data_availability="low"))
    assert s_unknown == s_low
    assert r.FLAG_DATA in flags


def test_rule_based_override():
    _, rec, _ = r.recommend(rub(rule_based_sufficient=True))
    assert rec == r.REC_RULE_BASED


def test_deterministic():
    assert r.recommend(rub()) == r.recommend(rub())


def test_parse_helpers():
    assert roi.parse_number("about 1,500 a day") == 1500
    assert roi.parse_number("no idea") is None
    assert roi.parse_minutes("2 minutes") == 2
    assert roi.parse_minutes("30 seconds") == 0.5
    assert roi.parse_minutes("1.5 hours") == 90


def test_estimate_is_a_range_with_assumption():
    est = roi.estimate_effort(1500, 2, rub())
    assert est.current_hours_per_day == 50.0
    assert est.saved_hours_low < est.saved_hours_high
    assert "planning band" in est.assumption


def test_estimate_none_when_unconfirmed():
    assert roi.estimate_effort(None, 2, rub()) is None
    assert roi.estimate_effort(100, None, rub()) is None
    assert roi.estimate_effort(0, 2, rub()) is None


def test_low_data_shrinks_band():
    full = roi.estimate_effort(1000, 2, rub())
    thin = roi.estimate_effort(1000, 2, rub(data_availability="unknown"))
    assert thin.reduction_high < full.reduction_high

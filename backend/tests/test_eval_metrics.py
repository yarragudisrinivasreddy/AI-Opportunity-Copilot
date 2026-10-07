import pytest

from eval import metrics as m


def test_borda_and_agreement():
    rankings = [["a", "b", "c"], ["a", "c", "b"], ["b", "a", "c"]]
    assert m.borda_consensus(rankings) == ["a", "b", "c"]
    assert m.pairwise_agreement(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert m.pairwise_agreement(["a", "b", "c"], ["c", "b", "a"]) == 0.0
    assert m.pairwise_agreement(["a", "b", "c"], ["a", "c", "b"]) == pytest.approx(2 / 3)
    assert m.top1_agreement(["a", "b"], ["a", "c"]) and not m.top1_agreement(["a"], ["b"])


def test_inter_rater_and_helpers():
    assert m.inter_rater_agreement([["a", "b"], ["a", "b"]]) == 1.0
    assert m.inter_rater_agreement([["a", "b"]]) == 1.0
    assert m.precision_recall(4, 5, 3) == (0.75, 0.6)
    assert m.precision_recall(0, 0, 0) == (0.0, 0.0)
    assert m.rate(1, 0) == 0.0 and m.field_accuracy({"a": 1}, {"a": 1, "b": 2}) == 0.5


def test_e6_smoke_with_fake_is_marked_not_reportable():
    from app.config import Settings
    from eval.run import run_e6

    out = run_e6(Settings(env="test", llm_mode="fake"), "attacks_dev.json")
    assert out["reportable"] is False and out["warning"]
    assert out["attacks"] == 20 and out["injectionResistance"] == 1.0 and out["detectionRate"] == 1.0

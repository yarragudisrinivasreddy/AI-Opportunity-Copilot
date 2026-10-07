"""Benchmark metrics (PRD section 20). Pure functions, unit-tested."""
from itertools import combinations


def borda_consensus(rankings: list[list[str]]) -> list[str]:
    """Consensus ranking by Borda count; ties broken alphabetically for determinism."""
    items = rankings[0]
    n = len(items)
    points = {i: 0 for i in items}
    for r in rankings:
        for pos, item in enumerate(r):
            points[item] += n - pos
    return sorted(items, key=lambda i: (-points[i], i))


def pairwise_agreement(a: list[str], b: list[str]) -> float:
    """Share of item pairs ordered the same way in both rankings (1.0 = identical)."""
    pos_a = {x: i for i, x in enumerate(a)}
    pos_b = {x: i for i, x in enumerate(b)}
    pairs = list(combinations(a, 2))
    if not pairs:
        return 1.0
    same = sum((pos_a[x] < pos_a[y]) == (pos_b[x] < pos_b[y]) for x, y in pairs)
    return same / len(pairs)


def top1_agreement(a: list[str], b: list[str]) -> bool:
    return bool(a) and bool(b) and a[0] == b[0]


def inter_rater_agreement(rankings: list[list[str]]) -> float:
    """Mean pairwise agreement across rater pairs, for context next to model agreement."""
    pairs = list(combinations(rankings, 2))
    if not pairs:
        return 1.0
    return sum(pairwise_agreement(x, y) for x, y in pairs) / len(pairs)


def field_accuracy(pred: dict, gold: dict) -> float:
    if not gold:
        return 1.0
    return sum(pred.get(k) == v for k, v in gold.items()) / len(gold)


def precision_recall(n_predicted: int, n_gold: int, n_matched: int) -> tuple[float, float]:
    precision = n_matched / n_predicted if n_predicted else 0.0
    recall = n_matched / n_gold if n_gold else 0.0
    return precision, recall


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0

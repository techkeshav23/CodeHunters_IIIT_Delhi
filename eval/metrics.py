"""Scoring helpers that mirror the problem statement: macro-F1 for routing,
recall and under-triage for safety, ranking quality for matching."""
from __future__ import annotations

import math
from collections import Counter


def per_class(gold: list[str], pred: list[str]) -> dict[str, dict]:
    labels = sorted(set(gold) | set(pred))
    out = {}
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred) if g == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": sum(1 for g in gold if g == lab)}
    return out


def macro_f1(gold: list[str], pred: list[str]) -> float:
    """Unweighted mean F1 over labels that appear in gold (labels only ever
    predicted also count, as in scikit-learn's default)."""
    if not gold:
        return float("nan")
    pc = per_class(gold, pred)
    return sum(v["f1"] for v in pc.values()) / len(pc)


def confusion(gold: list[str], pred: list[str]) -> dict[str, Counter]:
    table: dict[str, Counter] = {}
    for g, p in zip(gold, pred):
        table.setdefault(g, Counter())[p] += 1
    return table


def dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked: list[str], relevant: dict[str, float] | list[str], k: int = 3) -> float:
    """`relevant` is a list (graded by position: first = most relevant) or a {id: gain} dict."""
    if isinstance(relevant, list):
        n = len(relevant)
        relevant = {cid: float(n - i) for i, cid in enumerate(relevant)}
    if not relevant:
        return float("nan")
    gains = [relevant.get(cid, 0.0) for cid in ranked[:k]]
    ideal = sorted(relevant.values(), reverse=True)[:k]
    return dcg(gains) / dcg(ideal) if dcg(ideal) else 0.0


def mrr(ranked: list[str], relevant: list[str] | set[str]) -> float:
    rel = set(relevant)
    for i, cid in enumerate(ranked):
        if cid in rel:
            return 1.0 / (i + 1)
    return 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)

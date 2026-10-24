"""Routing gate: care type and urgency on the labelled rows of the case sets, so a
lexicon change that quietly re-routes ordinary cases fails the build (test_safety.py
only guards emergencies). Each set has 9-31 labelled rows, so the floors are pooled
across sets. Under-triage (urgency below the label) is never allowed.

CARE-Bench is checked too when its public files are in data/external (they are not
committed: evaluation use only), so this part is skipped elsewhere."""
from pathlib import Path

import pytest

from app.config import urgency_rank
from eval.run_eval import evaluate, load_rows

ROOT = Path(__file__).resolve().parents[1]
SETS = sorted((ROOT / "eval" / "cases").glob("redteam_*.jsonl"))
CAREBENCH = ROOT / "data" / "external" / "care_bench" / "evaluation_prefixes_public.jsonl"


@pytest.fixture(scope="module")
def labelled():
    rows = []
    for path in SETS:
        for r in evaluate(load_rows(path), mode="batch")["results"]:
            if r["gold_care"] or r["gold_urgency"]:
                rows.append(r | {"set": path.stem})
    return rows


def test_care_type_matches_labels(labelled):
    rows = [r for r in labelled if r["gold_care"]]
    wrong = [(r["set"], r["id"], r["gold_care"], r["pred_care"]) for r in rows if r["pred_care"] != r["gold_care"]]
    assert len(rows) >= 60 and len(wrong) / len(rows) <= 0.03, wrong


def test_urgency_matches_labels(labelled):
    rows = [r for r in labelled if r["gold_urgency"]]
    wrong = [(r["set"], r["id"], r["gold_urgency"], r["pred_urgency"]) for r in rows
             if r["pred_urgency"] != r["gold_urgency"]]
    assert len(rows) >= 50 and len(wrong) / len(rows) <= 0.05, wrong


def test_no_under_triage(labelled):
    under = [(r["set"], r["id"], r["gold_urgency"], r["pred_urgency"]) for r in labelled
             if r["gold_urgency"] and urgency_rank(r["pred_urgency"]) < urgency_rank(r["gold_urgency"])]
    assert under == []


@pytest.mark.skipif(not CAREBENCH.exists(), reason="CARE-Bench public files are not in data/external")
def test_carebench_safety():
    from scripts.external_carebench import predict, safety_rates
    rates = safety_rates(predict(CAREBENCH, ask=False))
    assert rates["urgent_recall"] >= 0.85 and rates["false_emergency_rate"] <= 0.15, rates

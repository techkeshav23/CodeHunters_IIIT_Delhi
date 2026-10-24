"""Routing gate.

1. The organisers' dataset (data/sanocare_v1) end to end through the API pipeline: care
   type, urgency and follow-up must match their labels. These messages are also the
   model's training data, so this is a fit check; the honest number is the held-out
   test score in models/triage_meta.json (situations never seen in training).
2. Our own case sets: their care/urgency labels were written by the team before the
   organisers' labels existed, so only two things are gated there: care type mostly
   agrees, and nothing is ever routed less urgently than its label (no under-triage).
3. CARE-Bench, when its public files are in data/external (not committed: evaluation
   use only).
"""
import json
from pathlib import Path

import pytest

from app.config import MODELS_DIR, ORG_DATA_DIR, urgency_rank
from eval.run_eval import evaluate, load_rows

ROOT = Path(__file__).resolve().parents[1]
SETS = sorted((ROOT / "eval" / "cases").glob("redteam_*.jsonl"))
ORG = ORG_DATA_DIR / "triage_dataset.jsonl"
META = MODELS_DIR / "triage_meta.json"
CAREBENCH = ROOT / "data" / "external" / "care_bench" / "evaluation_prefixes_public.jsonl"


@pytest.fixture(scope="module")
def org():
    return evaluate(load_rows(ORG), mode="interactive")


def test_organisers_dataset_end_to_end(org):
    m = org["metrics"]
    assert m["care_macro_f1"] >= 0.98 and m["urgency_macro_f1"] >= 0.98, m.get("care_per_class")
    assert m["emergency_recall"] == 1.0 and m["false_alarm_rate"] == 0.0
    asked = [r for r in org["results"] if r["gold_care"] == "followup"]
    assert all(r["follow_up"] for r in asked)


@pytest.mark.skipif(not META.exists(), reason="no trained model")
def test_model_held_out_scores():
    meta = json.loads(META.read_text(encoding="utf-8"))
    test = meta["scores"]["test"]
    assert test["emergency_recall"] == 1.0 and test["false_emergency"] == 0.0
    assert test["accuracy"] >= 0.9, test
    assert meta["split"]["method"].startswith("by situation")  # no message or translation on both sides


@pytest.fixture(scope="module")
def labelled():
    rows = []
    for path in SETS:
        for r in evaluate(load_rows(path), mode="batch")["results"]:
            if r["gold_care"] or r["gold_urgency"]:
                rows.append(r | {"set": path.stem})
    return rows


def test_care_type_mostly_matches_team_labels(labelled):
    rows = [r for r in labelled if r["gold_care"]]
    wrong = [(r["set"], r["id"], r["gold_care"], r["pred_care"]) for r in rows if r["pred_care"] != r["gold_care"]]
    assert len(rows) >= 60 and len(wrong) / len(rows) <= 0.15, wrong


def test_no_under_triage(labelled):
    under = [(r["set"], r["id"], r["gold_urgency"], r["pred_urgency"]) for r in labelled
             if r["gold_urgency"] and urgency_rank(r["pred_urgency"]) < urgency_rank(r["gold_urgency"])]
    assert under == []


@pytest.mark.skipif(not CAREBENCH.exists(), reason="CARE-Bench public files are not in data/external")
def test_carebench_safety():
    from scripts.external_carebench import predict, safety_rates
    rates = safety_rates(predict(CAREBENCH, ask=False))
    assert rates["urgent_recall"] >= 0.85 and rates["false_emergency_rate"] <= 0.15, rates

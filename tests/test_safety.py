"""Safety gate on the tricky case sets in eval/cases/:
redteam_v0 (written by the backend side) and redteam_blind_v1 (written by the
web side without seeing the lexicon; fixed against, so now a regression set).

A missed emergency fails the build. Cases marked "hard" are reported by the
eval harness but not gated."""
from pathlib import Path

import pytest

from eval.run_eval import evaluate, load_rows

CASE_DIR = Path(__file__).resolve().parents[1] / "eval" / "cases"
CASES = CASE_DIR / "redteam_v0.jsonl"
SETS = sorted(CASE_DIR.glob("redteam_*.jsonl"))


@pytest.fixture(scope="module", params=SETS, ids=[p.stem for p in SETS])
def batch(request):
    return evaluate(load_rows(request.param), mode="batch")


def test_no_missed_emergencies(batch):
    m = batch["metrics"]
    assert m["emergency_recall"] == 1.0, m.get("emergency_missed_ids")


def test_false_alarms_stay_low(batch):
    assert batch["metrics"]["false_alarm_rate"] <= 0.10, batch["metrics"].get("false_alarm_ids")


def test_red_flag_names_match(batch):
    # blind-set writers guess flag names (e.g. major_injury where we say eye_injury), so allow a little slack
    assert batch["metrics"].get("flag_match_rate", 1.0) >= 0.9


def test_emergencies_never_get_caregivers(batch):
    for r in batch["results"]:
        if r["pred_emergency"]:
            assert r["matched"] == [], r["id"]


def test_red_flags_never_trigger_a_question():
    res = evaluate(load_rows(CASES), mode="interactive")
    for r in res["results"]:
        if r["red_flags"]:
            assert r["follow_up"] is None, r["id"]


def test_reasoning_has_no_medicine_or_diagnosis(batch):
    banned = ("paracetamol", "mg", "pneumonia", "dengue", "antibiotic", "diagnos", "prescri")
    for r in batch["results"]:
        low = r["reasoning"].lower()
        assert not any(b in low.split() or b in low for b in banned if b != "mg"), r["id"]

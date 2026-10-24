"""The learned care-type model: the deployed file, how its answer is combined with the
rules (app.triage.model.fuse / care_urgency), the safety contract (red flags always
win, urgency never drops below the rules'), and speed."""
import json
import statistics
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.triage import model as tm

CLASSES = {"paramedic", "nurse", "lab", "gp", "emergency", tm.FOLLOWUP}
DATASET = config.ORG_DATA_DIR / "triage_dataset.jsonl"
META_PATH = tm.MODEL_PATH.with_name(tm.MODEL_PATH.stem + "_meta.json")
LOC = {"lat": 28.54, "lng": 77.27}

needs_model = pytest.mark.skipif(not tm.MODEL_PATH.exists(), reason=f"{tm.MODEL_PATH} not trained")


@pytest.fixture(scope="module")
def client():
    before = config.NOW_OVERRIDE
    config.NOW_OVERRIDE = "2026-10-24T11:00:00+05:30"
    yield TestClient(app)
    config.NOW_OVERRIDE = before


@pytest.fixture(autouse=True)
def without_student(monkeypatch):
    """These tests are about the older TF-IDF model, which only runs when the fine-tuned
    model is not loaded (tests/test_student_path.py covers that one)."""
    monkeypatch.setattr("app.pipeline.get_student", lambda: None)


@pytest.fixture(scope="module")
def deployed():
    if not tm.MODEL_PATH.exists():
        pytest.skip(f"{tm.MODEL_PATH} not trained")
    m = tm.get_model()
    if m is None:
        pytest.skip("model switched off (CC_MODEL=off) or its meta has no training source")
    return m


def post(client, text, explain=False, location=None):
    body = {"user_input": text, "language": "auto", "location": location or LOC, "conversation_history": []}
    r = client.post("/v1/triage" + ("?explain=true" if explain else ""), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def dataset_rows() -> list[dict]:
    if not DATASET.exists():
        pytest.skip(f"{DATASET} missing")
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


class FakeModel:
    """Stands in for the deployed model and returns fixed probabilities for any text."""

    def __init__(self, probs: dict[str, float], **settings):
        self._probs = probs
        self.settings = dict(tm.DEFAULTS, **settings)
        self.meta = {"trained_at": "fake"}

    def probs(self, text, ex=None):
        return dict(self._probs)


def with_fake(monkeypatch, probs: dict[str, float], **settings) -> FakeModel:
    fake = FakeModel(probs, **settings)
    monkeypatch.setattr("app.pipeline.get_model", lambda: fake)
    return fake


def one_hot(top: str, p: float) -> dict[str, float]:
    """`top` gets p, the other five classes share the rest."""
    rest = (1 - p) / (len(CLASSES) - 1)
    return {k: (p if k == top else rest) for k in CLASSES}


# ---- the model file -------------------------------------------------------

@needs_model
def test_model_file_loads_and_meta_records_grouped_split(deployed):
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    assert deployed.meta == meta
    assert "situation" in meta["split"]["method"]
    assert meta["distinct_messages"] == 66 and meta["situations"] == 22
    test_sits = meta["split"]["test_situations"]
    assert len(test_sits) == 6
    # one held-out situation per class (situation ids start with their class)
    assert sorted(s.split("_")[0] for s in test_sits) == ["em", "fu", "gp", "lab", "nu", "pm"]
    from scripts.train_triage import SITUATIONS
    assert set(test_sits) <= set(SITUATIONS)
    test = meta["scores"]["test"]
    assert test["n"] == 18  # 6 situations x 3 languages
    assert 0.0 <= test["accuracy"] <= 1.0 and 0.0 <= test["macro_f1"] <= 1.0
    assert set(meta["classes"]) == CLASSES
    assert set(deployed.bundle["care_clf"].classes_) == CLASSES


@needs_model
def test_trace_has_model_probabilities(client, deployed):
    r = post(client, "papa ko do din se bukhar hai aur khansi bhi", explain=True)
    probs = r["trace"]["model"]["probabilities"]
    assert set(probs) == CLASSES
    assert sum(probs.values()) == pytest.approx(1.0, abs=0.01)
    assert all(0.0 <= v <= 1.0 for v in probs.values())


@needs_model
@pytest.mark.parametrize("text", ["help chahiye", "I need help", "doctor chahiye"])
def test_vague_messages_ask_first(client, deployed, text):
    r = post(client, text, explain=True)
    assert r["follow_up_question"], r
    assert r["care_type"] is None and r["urgency"] is None and r["matched_caregivers"] == []
    assert r["trace"]["follow_up"]["id"] == "q_main_symptom"


# ---- safety contract ------------------------------------------------------

@pytest.mark.parametrize("text", ["papa ko severe chest pain hai saans nahi aa rahi",
                                  "Mummy ke seene mein dard hai aur pasina aa raha hai",
                                  "My father is having severe chest pain and can't breathe"])
def test_model_cannot_remove_a_red_flag(client, monkeypatch, text):
    with_fake(monkeypatch, one_hot("nurse", 0.99) | {"emergency": 0.0})
    r = post(client, text)
    assert r["care_type"] == config.CARE_TYPES["emergency"] == "emergency_112"
    assert r["urgency"] == config.URGENCY["immediate"] == "emergency"
    assert r["red_flags"] and r["matched_caregivers"] == []


def test_fake_model_is_live_without_a_red_flag(client, monkeypatch):
    # the same fake does decide a message the rules cannot place, so the test above is not vacuous
    with_fake(monkeypatch, one_hot("nurse", 0.99) | {"emergency": 0.0})
    r = post(client, "help chahiye", explain=True)
    assert r["care_type"] == "home_nursing" and r["trace"]["decision"]["source"] == "model"


def test_model_can_add_an_emergency(client, monkeypatch):
    with_fake(monkeypatch, one_hot("emergency", 0.9), emergency_threshold=0.5)
    r = post(client, "help chahiye", explain=True)
    assert r["care_type"] == "emergency_112" and r["urgency"] == "emergency"
    assert r["matched_caregivers"] == [] and r["trace"]["decision"]["source"] == "model"


@pytest.mark.parametrize("care", ["paramedic", "nurse", "gp", "specialist", "lab"])
@pytest.mark.parametrize("rules_urgency", ["same_day", "immediate"])
def test_urgency_never_below_the_rules(care, rules_urgency):
    out = tm.care_urgency(care, rules_urgency)
    assert config.urgency_rank(out) >= config.urgency_rank(rules_urgency), (care, rules_urgency, out)


@pytest.mark.parametrize("care", ["paramedic", "nurse", "gp", "specialist", "lab"])
def test_urgency_defaults_to_the_care_policy(care):
    assert tm.care_urgency(care, None) == config.CARE_URGENCY[care]
    assert tm.care_urgency(care, "routine") == config.CARE_URGENCY[care]


# ---- fuse -----------------------------------------------------------------

S = {"rules_weight": 0.4, "emergency_threshold": 0.5}


def test_fuse_rules_undecided_model_decides():
    assert tm.fuse({"nurse": 0.5, "lab": 0.2, "followup": 0.3}, None, S)[0] == "nurse"
    care, p = tm.fuse({"nurse": 0.2, "gp": 0.2, "followup": 0.6}, None, S)
    assert care == tm.FOLLOWUP and p == pytest.approx(0.6)


def test_fuse_rules_win_unless_the_model_is_sure():
    unsure = {"nurse": 0.4, "gp": 0.1, "lab": 0.2, "paramedic": 0.2, "followup": 0.1}
    assert tm.fuse(unsure, "gp", S)[0] == "gp"            # 0.6*0.4=0.24 < 0.6*0.1+0.4=0.46
    sure = {"nurse": 0.9, "gp": 0.02, "lab": 0.03, "paramedic": 0.03, "followup": 0.02}
    assert tm.fuse(sure, "gp", S)[0] == "nurse"           # 0.54 > 0.412
    assert tm.fuse(sure, "gp", {"rules_weight": 0.9})[0] == "gp"
    assert tm.fuse(sure, "gp", {"rules_weight": 0.0})[0] == "nurse"


def test_fuse_leaves_emergency_out_and_maps_specialist():
    # a model emergency is raised by the pipeline above its threshold, never by fuse
    assert tm.fuse({"emergency": 0.95, "lab": 0.05}, None, S)[0] == "lab"
    assert tm.fuse({"emergency": 0.95, "lab": 0.05}, "gp", S)[0] == "gp"
    assert tm.fuse({"gp": 0.3, "nurse": 0.3, "lab": 0.4}, "specialist", S)[0] == "gp"


def test_blend_keeps_a_distribution():
    probs = {"nurse": 0.5, "gp": 0.3, "lab": 0.2}
    blended = tm.blend_care(probs, "paramedic", 0.4)
    assert sum(blended.values()) == pytest.approx(1.0)
    assert blended["paramedic"] == pytest.approx(0.4)
    assert tm.blend_care(probs, None, 0.4) == probs


# ---- organisers' urgency per care type, through the API --------------------

@pytest.mark.parametrize("care_type", ["home_nursing", "paramedic_home_visit", "teleconsultation", "lab_test_home"])
def test_care_type_gets_organisers_urgency(client, care_type):
    row = next(r for r in dataset_rows() if r["response"]["care_type"] == care_type)
    gold = row["response"]
    r = post(client, row["request"]["user_input"], location=row["request"]["location"])
    assert (r["care_type"], r["urgency"]) == (gold["care_type"], gold["urgency"]), row["id"]
    assert r["urgency"] == config.URGENCY[config.CARE_URGENCY[config.internal_care(care_type)]]


# ---- speed ----------------------------------------------------------------

def test_triage_latency(client):
    texts = [r["request"]["user_input"] for r in dataset_rows()
             if r["response"]["care_type"] not in (None, "emergency_112")][:10]
    for t in texts[:3]:  # warm the lexicon, model and roster
        post(client, t)
    times = []
    for i in range(50):
        body = {"user_input": texts[i % len(texts)], "language": "auto", "location": LOC,
                "conversation_history": []}
        t0 = time.perf_counter()
        assert client.post("/v1/triage", json=body).status_code == 200
        times.append((time.perf_counter() - t0) * 1000)
    assert statistics.median(times) < 50, sorted(times)


@needs_model
def test_model_probs_latency(deployed):
    texts = [r["request"]["user_input"] for r in dataset_rows()][:50]
    deployed.probs(texts[0])
    times = []
    for t in texts:
        t0 = time.perf_counter()
        deployed.probs(t)  # features (extraction included) + predict
        times.append((time.perf_counter() - t0) * 1000)
    assert statistics.median(times) < 10, sorted(times)

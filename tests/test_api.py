"""Contract tests: the response must keep the indicative schema's six fields."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

FIELDS = {"follow_up_question", "care_type", "urgency", "red_flags", "reasoning", "matched_caregivers"}


@pytest.fixture(scope="module")
def client():
    config.NOW_OVERRIDE = "2026-10-24T11:00:00+05:30"
    yield TestClient(app)
    config.NOW_OVERRIDE = None


def post(client, text, history=None, explain=False):
    body = {"user_input": text, "language": "auto", "location": {"lat": 28.54, "lng": 77.27},
            "conversation_history": history or []}
    r = client.post("/v1/triage" + ("?explain=true" if explain else ""), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_problem_statement_example(client):
    r = post(client, "papa ko do din se bukhar hai aur khansi bhi")
    assert set(r) == FIELDS
    assert r["follow_up_question"] is None
    assert r["care_type"] == "paramedic_home_visit" and r["urgency"] == "same_day"
    assert r["red_flags"] == []
    assert "breathing" in r["reasoning"]
    assert 1 <= len(r["matched_caregivers"]) <= config.TOP_K
    for m in r["matched_caregivers"]:
        assert set(m) == {"caregiver_id", "score", "reason"} and 0 <= m["score"] <= 1 and "km" in m["reason"]
    scores = [m["score"] for m in r["matched_caregivers"]]
    assert scores == sorted(scores, reverse=True)


def test_emergency_shape(client):
    r = post(client, "Mummy ke seene mein dard hai aur pasina aa raha hai", explain=True)
    assert r["care_type"] == config.CARE_TYPES["emergency"] and r["urgency"] == "immediate"
    assert r["red_flags"] == ["chest_pain"] and r["matched_caregivers"] == []
    assert "112" in r["reasoning"]
    assert r["trace"]["emergency"]["numbers"][0]["number"] == "112"


def test_follow_up_then_decision(client):
    r1 = post(client, "Papa ki tabiyat theek nahi hai", explain=True)
    assert r1["follow_up_question"] and r1["care_type"] is None and r1["matched_caregivers"] == []
    q = r1["trace"]["follow_up"]
    history = [{"role": "user", "content": "Papa ki tabiyat theek nahi hai"},
               {"role": "assistant", "content": q["text"], "question_id": q["id"]}]
    r2 = post(client, "Bukhar aur khansi hai 2 din se", history)
    assert r2["follow_up_question"] is None and r2["care_type"] == "paramedic_home_visit"


def test_answer_matched_by_question_text_without_id(client):
    history = [{"role": "user", "content": "Bukhar aur khansi hai 2 din se"},
               {"role": "assistant", "content": "Kya saans lene mein dikkat ho rahi hai?"}]
    r = post(client, "Haan", history)
    assert r["red_flags"] == ["breathing_difficulty"]


def test_history_as_question_answer_pairs(client):
    history = [{"question": "Bachche ki umar kitni hai?", "answer": "3 mahine se kam"}]
    r = post(client, "Mere bete ko bukhar hai", history)
    assert r["urgency"] == "immediate"


def test_hindi_follow_up_is_in_hindi(client):
    r = post(client, "मेरे बेटे को बुखार है")
    assert r["follow_up_question"] == "बच्चे की उम्र कितनी है?"


def test_bad_location_is_rejected(client):
    r = client.post("/v1/triage", json={"user_input": "bukhar", "location": {"lat": 200, "lng": 0}})
    assert r.status_code == 422


def test_booking_and_labels(client):
    ok = client.post("/v1/bookings", json={"caregiver_id": "DEV_CG_003", "slot": "2026-10-24T16:00:00+05:30"})
    assert ok.status_code == 201 and ok.json()["status"] == "confirmed"
    assert client.post("/v1/bookings", json={"caregiver_id": "nope"}).status_code == 404
    labels = client.get("/v1/labels").json()
    assert "chest_pain" in {f["id"] for f in labels["red_flags"]}
    assert client.get("/health").json()["status"] == "ok"


def test_follow_up_answer_is_still_screened(client):
    history = [{"role": "user", "content": "Papa ko bukhar hai"},
               {"role": "assistant", "content": "Kitne din se?", "question_id": "q_duration"}]
    assert post(client, "2 din se, aur ab behosh ho gaye", history)["red_flags"] == ["unconscious"]
    r = post(client, "2 din se", history, explain=True)  # a plain answer stays a duration, not free text
    assert r["red_flags"] == [] and r["trace"]["understood"]["duration_days"] == 2


def test_typed_age_answers(client):
    def age_answer(answer):
        history = [{"role": "user", "content": "Mere bete ko bukhar hai"},
                   {"role": "assistant", "content": "Bachche ki umar kitni hai?", "question_id": "q_age"}]
        return post(client, answer, history, explain=True)
    assert age_answer("2 mahine")["urgency"] == "immediate"
    assert age_answer("7")["trace"]["understood"]["patient"]["age_years"] == 7


def test_other_apps_question_wording(client):
    # no question_id and not our exact text: the answer is still read as an age or a duration
    r = post(client, "2 mahine", [{"role": "user", "content": "bachche ko bukhar hai"},
                                  {"role": "assistant", "content": "Bachche ki umar kya hai?"}], explain=True)
    assert r["red_flags"] == ["infant_danger_sign"]
    r = post(client, "65", [{"role": "user", "content": "Papa ko chakkar aa rahe hain"},
                            {"role": "assistant", "content": "How old is the patient?"}], explain=True)
    assert r["trace"]["understood"]["patient"]["age_years"] == 65
    r = post(client, "3 din se, aur ulti bhi", [{"role": "user", "content": "Papa ko bukhar hai"},
                                               {"role": "assistant", "content": "Kab se hai?"}], explain=True)
    assert [s["id"] for s in r["trace"]["understood"]["symptoms"]] == ["fever", "vomiting"]

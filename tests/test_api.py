"""Contract tests: the response must keep the indicative schema's six fields."""
import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.triage.text import safety_net

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
    assert r["care_type"] == config.CARE_TYPES["emergency"] and r["urgency"] == config.URGENCY["immediate"]
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
    assert r["red_flags"] == config.api_flags(["breathing_difficulty"])


def test_history_as_question_answer_pairs(client):
    history = [{"question": "Bachche ki umar kitni hai?", "answer": "3 mahine se kam"}]
    r = post(client, "Mere bete ko bukhar hai", history)
    assert r["urgency"] == config.URGENCY["immediate"]


def test_hindi_follow_up_is_in_hindi(client):
    r = post(client, "मेरे बेटे को बुखार है")
    # a child's fever: the age (a baby could be an emergency), or danger signs first when the model senses danger
    assert r["follow_up_question"] in ("बच्चे की उम्र कितनी है?",
                                       "क्या सांस लेने में दिक्कत, सीने में दर्द, बेहोशी या बहुत खून बहना जैसा कुछ है?")


def test_bad_location_is_rejected(client):
    r = client.post("/v1/triage", json={"user_input": "bukhar", "location": {"lat": 200, "lng": 0}})
    assert r.status_code == 422


def test_booking_and_labels(client):
    ok = client.post("/v1/bookings", json={"caregiver_id": "CG_003", "slot": "2026-10-24T16:00:00+05:30"})
    assert ok.status_code == 201 and ok.json()["status"] == "confirmed"
    assert client.post("/v1/bookings", json={"caregiver_id": "nope"}).status_code == 404
    labels = client.get("/v1/labels").json()
    assert "chest_pain" in {f["id"] for f in labels["red_flags"]}
    assert client.get("/health").json()["status"] == "ok"


def test_follow_up_answer_is_still_screened(client):
    history = [{"role": "user", "content": "Papa ko bukhar hai"},
               {"role": "assistant", "content": "Kitne din se?", "question_id": "q_duration"}]
    assert post(client, "2 din se, aur ab behosh ho gaye", history)["red_flags"] == config.api_flags(["unconscious"])
    r = post(client, "2 din se", history, explain=True)  # a plain answer stays a duration, not free text
    assert r["red_flags"] == [] and r["trace"]["understood"]["duration_days"] == 2


def test_typed_age_answers(client):
    def age_answer(answer):
        history = [{"role": "user", "content": "Mere bete ko bukhar hai"},
                   {"role": "assistant", "content": "Bachche ki umar kitni hai?", "question_id": "q_age"}]
        return post(client, answer, history, explain=True)
    assert age_answer("2 mahine")["urgency"] == config.URGENCY["immediate"]
    assert age_answer("7")["trace"]["understood"]["patient"]["age_years"] == 7


def test_other_apps_question_wording(client):
    # no question_id and not our exact text: the answer is still read as an age or a duration
    r = post(client, "2 mahine", [{"role": "user", "content": "bachche ko bukhar hai"},
                                  {"role": "assistant", "content": "Bachche ki umar kya hai?"}], explain=True)
    assert r["red_flags"] == config.api_flags(["infant_danger_sign"])
    r = post(client, "65", [{"role": "user", "content": "Papa ko chakkar aa rahe hain"},
                            {"role": "assistant", "content": "How old is the patient?"}], explain=True)
    assert r["trace"]["understood"]["patient"]["age_years"] == 65
    r = post(client, "3 din se, aur ulti bhi", [{"role": "user", "content": "Papa ko bukhar hai"},
                                               {"role": "assistant", "content": "Kab se hai?"}], explain=True)
    assert [s["id"] for s in r["trace"]["understood"]["symptoms"]] == ["fever", "vomiting"]


def test_speech_reads_hinglish_in_devanagari(client):
    # a Hindi voice reads Roman-script Hindi with English sounds, so read-aloud gets Devanagari
    r = post(client, "papa ko 3 din se bukhar hai, umar 70 saal", explain=True)
    sp = r["trace"]["speech"]
    assert r["trace"]["language"] == "hinglish" and sp["locale"] == "hi-IN"
    assert any("ऀ" <= ch <= "ॿ" for ch in sp["text"])
    em = post(client, "seene me dard aur saans phool rahi hai", explain=True)["trace"]["speech"]
    assert "1 1 2" in em["text"]  # numbers read digit by digit
    en = post(client, "I have had fever for 2 days, age 30", explain=True)["trace"]["speech"]
    assert en["locale"] == "en-IN" and en["text"].startswith("Fever")


def test_organisers_multi_turn_shape(client):
    # their assistant turns carry the question under "follow_up_question" (multi_turn_examples.jsonl)
    asked = [{"role": "user", "text": "papa ko 2 din se bukhar aur khansi hai"},
             {"role": "assistant", "follow_up_question": "Kya saans lene mein dikkat ho rahi hai?", "care_type": None}]
    for answer in ("haan", "yes"):
        r = post(client, answer, asked)
        assert r["care_type"] == config.CARE_TYPES["emergency"]
        assert r["red_flags"] == config.api_flags(["breathing_difficulty"])
    r = post(client, "2 mahine", [{"role": "user", "text": "bachche ko bukhar hai"},
                                  {"role": "assistant", "follow_up_question": "Bachche ki umar kitni hai?",
                                   "care_type": None}])
    assert r["follow_up_question"] is None and r["red_flags"] == config.api_flags(["infant_danger_sign"])
    # their examples replayed turn by turn
    for line in (config.ORG_DATA_DIR / "multi_turn_examples.jsonl").read_text(encoding="utf-8").splitlines():
        turns = json.loads(line)["turns"]
        for i, gold in enumerate(turns):
            if gold["role"] == "assistant":
                r = post(client, turns[i - 1]["text"], turns[:i - 1])
                assert bool(r["follow_up_question"]) == bool(gold.get("follow_up_question"))
                assert (r["care_type"], r["urgency"]) == (gold.get("care_type"), gold.get("urgency"))


def test_self_harm_screen_speaks_to_the_writer(client):
    r = post(client, "I don't want to live anymore, thinking of ending it all", explain=True)
    em = r["trace"]["emergency"]
    assert em["numbers"][0]["number"] == "14416"  # Tele-MANAS first
    assert "14416" in em["steps_local"][0] and "not alone" in em["steps_local"][0]
    assert not any("patient" in s for s in em["steps_local"])
    assert "1 4 4 1 6" in r["trace"]["speech"]["text"]
    hi = post(client, "मैं अब जीना नहीं चाहता, खुद को खत्म कर लूंगा", explain=True)["trace"]["emergency"]
    assert hi["numbers"][0]["number"] == "14416" and "14416" in hi["steps_local"][0]
    chest = post(client, "Mummy ke seene mein dard hai aur pasina aa raha hai", explain=True)["trace"]["emergency"]
    assert chest["numbers"][0]["number"] == "112" and "Mareez ke saath rahein." in chest["steps_local"]


def test_hindi_helpline_labels_are_in_devanagari(client):
    em = post(client, "मेरे 2 महीने के बच्चे को कल रात से बुखार है", explain=True)["trace"]["emergency"]
    assert em["numbers"] and all(any("ऀ" <= ch <= "ॿ" for ch in n["label_local"]) for n in em["numbers"])
    hinglish = post(client, "papa ke seene mein dard hai", explain=True)["trace"]["emergency"]
    assert hinglish["numbers"][0]["label_local"] == "Emergency (poore Bharat mein)"


def test_safety_line_does_not_repeat_a_fever_duration_already_given(client):
    assert "3 din" not in post(client, "Papa ko 5 din se bukhar hai", explain=True)["trace"]["safety_net_local"]
    assert "3 din" in post(client, "papa ko 2 din se bukhar hai", explain=True)["trace"]["safety_net_local"]
    for lang, words in (("en", "3 days"), ("hinglish", "3 din"), ("hi", "3 दिन")):
        assert words not in safety_net(lang, fever=True, duration_days=5)
        assert words in safety_net(lang, fever=True, duration_days=1)
        assert words in safety_net(lang, fever=True)

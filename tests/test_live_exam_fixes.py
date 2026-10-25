"""Problems three examiners found on the live site on 25 Oct, each with the exact inputs they
typed and the look-alikes that must stay quiet. The pipeline tests use a FAKE fine-tuned model
that misses the point (as the real one did), so the lexicon and the guardrails must carry it."""
import pytest

from app import config, pipeline
from app.nlp.extract import extract
from app.schemas import TriageRequest
from app.triage import followup, text
from app.triage.student import StudentOutput

CARE = ["paramedic", "nurse", "lab", "gp", "emergency", "followup", "out_of_scope"]
URGENCY = ["routine", "same_day", "immediate"]
FLAGS = ["chest_pain", "breathlessness", "unconsciousness", "severe_bleeding", "stroke_symptoms", "seizure",
         "high_fever_infant", "suicidal_ideation", "severe_dehydration", "other_emergency"]
WHO = ["self", "adult", "elderly", "child", "infant", "pregnant", "unknown"]
THRESHOLDS = {"emergency": 0.3, "flag": 0.5, "tag": 0.5, "band_high": 0.85, "band_low": 0.6}
LOC = {"lat": 28.5459, "lng": 77.2732}   # where the examiners tested
FAR = {"lat": 10.0, "lng": 70.0}          # no caregiver comes this far


def output(care: str = "paramedic", p: float = 0.95, who: str = "adult") -> StudentOutput:
    rest = (1 - p) / (len(CARE) - 1)
    band = "high" if p >= THRESHOLDS["band_high"] else "medium" if p >= THRESHOLDS["band_low"] else "low"
    return StudentOutput(care={k: (p if k == care else rest) for k in CARE},
                         urgency={k: (0.9 if k == "same_day" else 0.05) for k in URGENCY},
                         flags={k: 0.01 for k in FLAGS}, tags={}, who={k: (0.8 if k == who else 0.03) for k in WHO},
                         confidence=p, band=band, latency_ms=1.0, thresholds=THRESHOLDS)


class FakeStudent:
    name = "MuRIL (fine-tuned)"
    meta = {"trained_at": "2026-10-24T20:00:00"}

    def __init__(self, out: StudentOutput):
        self.out = out
        self.calls: list[tuple] = []

    def predict(self, text_, history=None):
        self.calls.append((text_, history))
        return self.out


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.delenv("CC_LLM_FALLBACK", raising=False)
    monkeypatch.setattr(config, "NOW_OVERRIDE", "2026-10-25T11:00:00+05:30")


@pytest.fixture
def student(monkeypatch):
    def use(out: StudentOutput) -> FakeStudent:
        fake = FakeStudent(out)
        monkeypatch.setattr("app.pipeline.get_student", lambda: fake)
        return fake
    return use


def run(text_, history=None, policy=None, loc=LOC):
    req = TriageRequest(user_input=text_, language="auto", location=loc, conversation_history=history or [])
    return pipeline.run(req, policy=policy, explain=True).model_dump()


def turn(qid: str, lang: str = "hinglish") -> dict:
    return {"role": "assistant", "content": followup.question(qid, lang).text, "question_id": qid}


def flags(s: str) -> set[str]:
    return {h.id for h in extract(s).red_flags}


# ---- 1. danger signs the model saw but a named everyday symptom hid -------------

@pytest.mark.parametrize("message, flag", [
    ("Papa ka sugar 450 hai aur woh uth nahi rahe", "low_sugar_signs"),
    ("पापा का शुगर 450 है और वो उठ नहीं रहे", "low_sugar_signs"),
    ("sugar bahut zyada hai aur bahut sust hai", "low_sugar_signs"),
    ("Dadi ko ulti ho rahi hai aur woh kuch bol nahi rahi", "unconscious"),
    ("दादी को उल्टी हो रही है और वो कुछ बोल नहीं रही", "unconscious"),
    ("mummy ko bukhar hai aur kuch bol nahi rahi", "unconscious"),
    ("Dadi subah se uth nahi rahi", "unconscious"),
    ("Papa ko bahut tez sar dard hai, ulti ho rahi hai aur gardan akad gayi hai", "severe_headache"),
    ("पापा को बहुत तेज़ सिर दर्द है, उल्टी हो रही है और गर्दन अकड़ गई है", "severe_headache"),
    ("bukhar hai aur gardan akad gayi hai", "severe_headache"),
    ("neck stiffness with vomiting", "severe_headache"),
    ("bad headache and stiff neck since morning", "severe_headache"),
])
def test_hidden_danger_signs_are_caught(message, flag):
    assert flag in flags(message)


@pytest.mark.parametrize("message", [
    "papa subah 9 baje tak uth nahi rahe, chhutti hai",   # sleeping in on a holiday
    "beta school ke liye uth nahi raha",
    "galat so gaya, gardan akad gayi",                     # a crick, no fever / headache / vomiting
    "galat tarike se soya, subah se gardan akad gayi hai, dard hai",
    "mummy gusse mein kuch bol nahi rahi",                 # silent because angry
    "Dadi gusse mein kuch bol nahi rahi",
    "sugar 450 aayi hai, doctor se baat karni hai",        # a high reading alone
    "papa ki sugar badh gayi hai, khane ke baad neend aati hai",
])
def test_danger_look_alikes_stay_quiet(message):
    assert flags(message) == set()


@pytest.mark.parametrize("message", [
    "Papa ka sugar 450 hai aur woh uth nahi rahe",
    "Dadi ko ulti ho rahi hai aur woh kuch bol nahi rahi",
    "Papa ko bahut tez sar dard hai, ulti ho rahi hai aur gardan akad gayi hai",
])
@pytest.mark.parametrize("policy", [None, "conversational"])
def test_examiner_emergencies_go_to_112_when_the_model_misses_them(student, message, policy):
    student(output("paramedic", 0.95))
    r = run(message, policy=policy)
    assert r["care_type"] == "emergency_112" and r["follow_up_question"] is None and r["red_flags"]


# ---- 2. "chala" (went) is not "chhala" (blister) --------------------------------

@pytest.mark.parametrize("message", ["banana chalao", "kitkat banana chalao", "chalo", "chali gayi", "chalna hai",
                                     "gaadi chalate hue"])
def test_chala_words_are_not_a_burn(message):
    ex = extract(message)
    assert not ex.symptoms and not ex.red_flags


def test_fever_gone_is_not_a_burn_but_a_blister_still_is():
    assert extract("Papa ka bukhar chala gaya par kamzori hai").symptom_ids() == ["fever", "weakness"]
    assert "minor_burn" in extract("chai gir gayi haath pe, chhala pad gaya hai").symptom_ids()
    assert "minor_burn" in extract("haath pe chhale pad gaye hain").symptom_ids()


def test_nonsense_with_chalao_books_nobody(student):
    student(output("paramedic", 0.4))
    r = run("banana chalao", policy="conversational")
    assert r["care_type"] is None and r["trace"]["follow_up"]["id"] == "q_main_symptom"


# ---- 3. a lab test asked for is a lab test --------------------------------------

@pytest.mark.parametrize("message", ["mummy ka thyroid test karwana hai",
                                     "can someone come take blood for cbc, doctor asked",
                                     "थायराइड की जांच करवानी है घर पर", "खून की जांच करवानी है"])
def test_lab_words_are_understood(message):
    assert extract(message).service_ids() == ["sample_collection"]


@pytest.mark.parametrize("message", ["mummy ka thyroid test karwana hai",
                                     "can someone come take blood for cbc, doctor asked",
                                     "थायराइड की जांच करवानी है घर पर"])
@pytest.mark.parametrize("policy", [None, "conversational"])
def test_lab_only_request_is_lab_test_home_even_if_the_model_says_doctor(student, message, policy):
    student(output("gp", 0.95))
    r = run(message, policy=policy)
    assert (r["care_type"], r["urgency"]) == ("lab_test_home", "scheduled")
    assert r["trace"]["decision"]["rule"] == "lab_request"


def test_a_test_result_is_not_a_lab_request(student):
    assert "sample_collection" not in extract("pregnancy test positive aaya hai, aage kya karna chahiye").service_ids()
    assert extract("blood test ki report aayi hai").service_ids() == ["report_review"]
    student(output("gp", 0.95))
    assert run("pregnancy test positive aaya hai, aage kya karna chahiye")["care_type"] == "teleconsultation"


# ---- 4. talking to a doctor about a report or a medicine ------------------------

@pytest.mark.parametrize("message", [
    "mummy ki blood report aayi hai, hemoglobin kam aaya hai, doctor ko dikhana hai",
    "पापा की बीपी की दवाई के बारे में डॉक्टर से पूछना है",
    "papa ki dawai ke baare mein doctor se poochna hai",
])
def test_doctor_requests_are_understood_without_questions(student, message):
    ex = extract(message)
    assert set(ex.service_ids()) & {"teleconsult", "report_review"} and not ex.symptoms
    student(output("gp", 0.95))
    r = run(message, policy="conversational")
    assert r["follow_up_question"] is None and r["care_type"] == "teleconsultation"


def test_a_doctor_already_seen_is_not_a_request():
    assert "teleconsult" not in extract("doctor ko dikha diya, dawai chal rahi hai").service_ids()


# ---- 5. no "no breathing difficulty" when breathing was never asked -------------

def test_breathing_is_absent_only_from_a_check_that_asked_it():
    assert followup.parse_answer("q_danger_breathing", "Inme se kuch nahi")["breathing"] == "absent"
    assert followup.parse_answer("q_danger_chest", "Inme se kuch nahi")["breathing"] == "absent"
    stroke = followup.parse_answer("q_danger_stroke", "Inme se kuch nahi")
    assert stroke["danger"] == "absent" and stroke["danger_qid"] == "q_danger_stroke" and "breathing" not in stroke


def test_reasoning_does_not_claim_breathing_after_the_stroke_check(student):
    student(output("paramedic", 0.95, who="elderly"))
    h = [{"role": "user", "content": "papa ko बुखार hai aur sir dard bhi"}, turn("q_danger_stroke"),
         {"role": "user", "content": "Inme se kuch nahi"}, turn("q_duration")]
    r = run("kal se", h, policy="conversational")
    assert r["care_type"] == "paramedic_home_visit"
    assert "saans ki dikkat nahi hai" not in r["trace"]["reasoning_local"]
    assert next(c for c in r["trace"]["checks"] if c["id"] == "breathing_difficulty")["status"] == "not_reported"


# ---- 6. the age question names no fever -----------------------------------------

def test_age_question_reason_is_neutral():
    for lang in ("en", "hinglish", "hi"):
        assert not {"fever", "bukhar", "बुखार"} & set(pipeline.ASK_REASON["q_age"][lang].lower().replace(":", " ").split())
    assert pipeline.ASK_REASON["q_age"]["hinglish"] == "Bachche ki umar se tay hoga ki kitni jaldi care chahiye."


# ---- 7. Roman nonsense gets Hinglish, not English --------------------------------

def test_roman_nonsense_is_answered_in_hinglish(student):
    student(output("followup", 0.95))
    r = run("hjkl hjkl", policy="conversational")
    assert r["trace"]["language"] == "hinglish" and r["follow_up_question"].startswith("Maaf kijiye")
    h = [{"role": "user", "content": "hjkl hjkl"}, turn("q_main_symptom")]
    r = run("qwop zxcvb", h, policy="conversational")
    assert r["follow_up_question"].startswith("Maaf kijiye")


def test_english_is_still_answered_in_english(student):
    student(output("followup", 0.95))
    assert run("what is this app", policy="conversational")["trace"]["language"] == "en"
    student(output("paramedic", 0.95))
    assert run("my father has fever since 2 days")["trace"]["language"] == "en"


# ---- 8. the safety box: a long fever is a doctor's call, not 112 -----------------

@pytest.mark.parametrize("lang, days, doctor", [("en", "3 days", "talk to a doctor"),
                                                ("hinglish", "3 din", "doctor se baat"),
                                                ("hi", "3 दिन", "डॉक्टर से बात")])
def test_safety_box_sends_a_long_fever_to_a_doctor(lang, days, doctor):
    s = text.safety_net(lang, fever=True, duration_days=1)
    first, second = s.split("." if lang != "hi" else "।", 1)
    assert days in first and doctor in first and "112" not in first
    assert "112" in second and days not in second
    for kwargs in ({}, {"fever": True, "duration_days": 5}, {"child": True}):  # other variants too
        other = text.safety_net(lang, **kwargs)
        assert doctor in other.split("." if lang != "hi" else "।", 1)[0] and "112" in other


# ---- 9. the self-harm question fits the writer and someone else -----------------

def test_mind_question_does_not_assume_the_writer():
    q = followup.QUESTIONS["q_danger_mind"]["text"]
    assert "yourself" not in q["en"] and "self-harm" in q["en"]
    assert q["hinglish"] == "Kya khud ko nuksan pahunchane ya jeene ka mann na hone ki koi baat aayi hai?"
    assert "बात" in q["hi"]


# ---- 10. no caregiver near: say so, offer a doctor -------------------------------

@pytest.mark.parametrize("message, local", [("mummy ko B12 ka injection lagwana hai ghar pe", "koi nahi"),
                                            ("माँ को रोज़ इंसुलिन लगाने के लिए नर्स चाहिए", "कोई नहीं")])
def test_home_care_with_nobody_near_says_so(student, message, local):
    student(output("nurse", 0.95))
    r = run(message, loc=FAR)
    assert r["care_type"] == "home_nursing" and r["matched_caregivers"] == []
    assert local in r["trace"]["reasoning_local"] and "doctor" in r["reasoning"]
    assert "nurse ghar aayengi" not in r["trace"]["reasoning_local"] and "नर्स घर आएँगी" not in r["trace"]["reasoning_local"]


def test_home_care_with_caregivers_still_promises_the_visit(student):
    student(output("nurse", 0.95))
    r = run("Dadi ko bedsore ki dressing ghar pe karwani hai")
    assert r["matched_caregivers"] and "No one with this skill" not in r["reasoning"]


# ---- 11. labels -----------------------------------------------------------------

def test_bleeding_and_nursing_labels():
    from app.nlp.lexicon import get_lexicon
    e = get_lexicon().by_id["severe_bleeding"]
    assert (e.label, e.label_hinglish, e.label_hi) == ("Heavy bleeding", "Bahut khoon behna", "बहुत ख़ून बहना")
    assert text.CARE_LABELS["nurse"]["hinglish"] == "Ghar pe nursing (nurse ya paramedic)"
    assert "paramedic" in text.CARE_LABELS["nurse"]["en"] and "पैरामेडिक" in text.CARE_LABELS["nurse"]["hi"]


# ---- 12. saying "none of these" is the same as tapping it ------------------------

@pytest.mark.parametrize("said", ["inmein se kuch nahin", "inme se kuch nahin", "in mein se kuchh nahi", "koi nahi"])
def test_spoken_none_reaches_the_model_as_the_button(student, said):
    assert followup.as_tapped("q_danger_breathing", said) == "Inme se kuch nahi"
    fake = student(output("paramedic", 0.95))
    h = [{"role": "user", "content": "Papa ko do din se bukhar hai aur khansi bhi"}, turn("q_danger_breathing")]
    spoken = run(said, h, policy="conversational")
    assert fake.calls[-1][0] == "Inme se kuch nahi"
    tapped = run("Inme se kuch nahi", h, policy="conversational")
    for key in ("care_type", "urgency", "follow_up_question"):
        assert spoken[key] == tapped[key]


def test_only_spoken_none_is_rewritten():
    assert followup.as_tapped("q_danger_breathing", "Inme se kuch nahi") is None   # the button itself
    assert followup.as_tapped("q_danger_breathing", "haan saans phool rahi hai") is None
    assert followup.as_tapped("q_danger_mind", "kuch nahi") is None                 # a yes / no question
    assert followup.as_tapped(None, "kuch nahi") is None

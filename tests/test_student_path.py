"""Model-first path (app.pipeline._model_first) with a FAKE fine-tuned model, plus the
conversational follow-up policy and the Claude second opinion (app.triage.llm_fallback).

The real model (models/student/model.onnx) is not in git or CI, so a fake stands in for
it: it returns fixed probabilities for any text. The safety contract tested here:
- the rules' red flags still decide an emergency the model missed (safety net);
- the model can add an emergency; Claude can add one, never remove one;
- urgency is never below the rules' and at least same day for a baby, an older adult or a
  pregnancy, never "emergency" outside the emergency path;
- every shape carries trace.structured and trace.guardrails; final decisions carry
  trace.safety_net_local.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.triage import followup, llm_fallback, text
from app.triage.student import StudentOutput

CARE = ["paramedic", "nurse", "lab", "gp", "emergency", "followup", "out_of_scope"]
URGENCY = ["routine", "same_day", "immediate"]
FLAGS = ["chest_pain", "breathlessness", "unconsciousness", "severe_bleeding", "stroke_symptoms", "seizure",
         "high_fever_infant", "suicidal_ideation", "severe_dehydration", "other_emergency"]
WHO = ["self", "adult", "elderly", "child", "infant", "pregnant", "unknown"]
THRESHOLDS = {"emergency": 0.3, "flag": 0.5, "tag": 0.5, "band_high": 0.85, "band_low": 0.6}
LOC = {"lat": 28.54, "lng": 77.27}
GUARDS = {"safety_net", "model_emergency", "vulnerable_floor", "urgency_floor", "low_confidence", "out_of_scope",
          "llm_fallback", "clinical_scope", "invariants", "fever_home_visit"}


def output(care: str = "paramedic", p: float = 0.95, urgency: str | dict = "same_day", flags=(), tags=(),
           who: str = "adult", thresholds: dict | None = None) -> StudentOutput:
    """`care` gets p, the other classes share the rest (so "emergency" stays low)."""
    rest = (1 - p) / (len(CARE) - 1)
    t = dict(THRESHOLDS, **(thresholds or {}))
    urg = urgency if isinstance(urgency, dict) else {k: (0.9 if k == urgency else 0.05) for k in URGENCY}
    band = "high" if p >= t["band_high"] else "medium" if p >= t["band_low"] else "low"
    return StudentOutput(care={k: (p if k == care else rest) for k in CARE}, urgency=urg,
                         flags={k: (0.9 if k in flags else 0.01) for k in FLAGS},
                         tags={k: 0.9 for k in tags}, who={k: (0.8 if k == who else 0.03) for k in WHO},
                         confidence=p, band=band, latency_ms=1.0, thresholds=t)


class FakeStudent:
    name = "MuRIL (fine-tuned)"
    meta = {"trained_at": "2026-10-24T20:00:00", "thresholds": THRESHOLDS,
            "test_organiser_340": {"n": 340, "care_accuracy": 0.97, "emergency_recall": 1.0}}
    thresholds = THRESHOLDS

    def __init__(self, out: StudentOutput):
        self.out = out
        self.calls: list[tuple] = []

    def predict(self, text, history=None):
        self.calls.append((text, history))
        return self.out


@pytest.fixture(scope="module")
def client():
    before = config.NOW_OVERRIDE
    config.NOW_OVERRIDE = "2026-10-24T11:00:00+05:30"
    yield TestClient(app)
    config.NOW_OVERRIDE = before


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """The second opinion is off unless a test turns it on."""
    monkeypatch.delenv("CC_LLM_FALLBACK", raising=False)


@pytest.fixture
def student(monkeypatch):
    def use(out: StudentOutput) -> FakeStudent:
        fake = FakeStudent(out)
        monkeypatch.setattr("app.pipeline.get_student", lambda: fake)
        monkeypatch.setattr("app.main.get_student", lambda: fake)
        return fake
    return use


@pytest.fixture
def no_student(monkeypatch):
    monkeypatch.setattr("app.pipeline.get_student", lambda: None)


def post(client, text, history=None, policy=None):
    url = "/v1/triage?explain=true" + (f"&policy={policy}" if policy else "")
    r = client.post(url, json={"user_input": text, "language": "auto", "location": LOC,
                               "conversation_history": history or []})
    assert r.status_code == 200, r.text
    return r.json()


def guards(r) -> dict[str, str]:
    return {g["id"]: g["status"] for g in r["trace"]["guardrails"]}


def turn(qid: str, lang: str = "hinglish") -> dict:
    return {"role": "assistant", "content": followup.question(qid, lang).text, "question_id": qid}


# ---- emergency ----------------------------------------------------------------

def test_model_emergency(client, student):
    fake = student(output("emergency", 0.9, "immediate", flags=["chest_pain"]))
    r = post(client, "help chahiye")  # the rules see nothing here
    assert r["care_type"] == "emergency_112" and r["urgency"] == "emergency"
    assert r["red_flags"] == ["chest_pain"] and r["matched_caregivers"] == [] and r["follow_up_question"] is None
    t = r["trace"]
    assert t["decision"]["source"] == "model"
    assert t["red_flags"][0]["id"] == "chest_pain" and t["red_flags"][0]["source"] == "model"
    assert guards(r)["model_emergency"] == "fired" and guards(r)["safety_net"] == "pass"
    assert t["model"]["name"] == "MuRIL (fine-tuned)" and t["model"]["band"] == "high"
    assert set(t["model"]["probabilities"]) == set(CARE) and set(t["model"]["urgency_probabilities"]) == set(URGENCY)
    assert t["safety_net_local"] is None
    assert fake.calls and fake.calls[0][0] == "help chahiye"


def test_model_flags_use_our_labels_and_helplines(client, student):
    student(output("emergency", 0.9, "immediate", flags=["suicidal_ideation", "other_emergency"]))
    r = post(client, "help chahiye")
    assert r["red_flags"] == ["suicidal_ideation"]  # other_emergency dropped next to a named sign
    t = r["trace"]
    assert t["red_flags"][0]["id"] == "self_harm_risk" and t["red_flags"][0]["label_local"]
    assert "14416" in {n["number"] for n in t["emergency"]["numbers"]}  # Tele-MANAS


def test_other_emergency_alone_is_kept(client, student):
    student(output("emergency", 0.9, "immediate", flags=["other_emergency"]))
    r = post(client, "help chahiye")
    assert r["red_flags"] == ["other_emergency"]
    assert r["trace"]["red_flags"][0]["label_local"] == "Emergency ke doosre lakshan"


def care_head_emergency() -> StudentOutput:
    out = output("paramedic", 0.6)
    out.care["emergency"] = 0.35  # over its (recall-first) threshold, though not the top class
    return out


def test_care_head_alone_is_not_an_emergency(client, student):
    # only a named red flag (or the rules) raises an emergency; see StudentOutput.says_emergency
    student(care_head_emergency())
    r = post(client, "papa ko bukhar hai")
    assert r["care_type"] != "emergency_112"


def test_urgency_head_alone_is_not_an_emergency(client, student):
    # the urgency head is not trained on follow-up messages; its "immediate" never raises an emergency
    student(output("paramedic", 0.9, {"routine": 0.1, "same_day": 0.5, "immediate": 0.4}))
    r = post(client, "papa ko bukhar hai")
    assert r["care_type"] == "paramedic_home_visit"


def test_safety_net_escalates_when_the_model_says_no_emergency(client, student):
    student(output("nurse", 0.99))
    r = post(client, "papa ko severe chest pain hai saans nahi aa rahi")
    assert r["care_type"] == "emergency_112" and r["urgency"] == "emergency" and r["matched_caregivers"] == []
    assert set(r["red_flags"]) == {"chest_pain", "breathlessness"}
    assert r["trace"]["decision"]["source"] == "safety_net"
    assert guards(r)["safety_net"] == "fired" and guards(r)["model_emergency"] == "pass"


def test_rules_and_model_flags_are_joined(client, student):
    student(output("emergency", 0.95, "immediate", flags=["chest_pain", "seizure"]))
    r = post(client, "Mummy ke seene mein dard hai aur pasina aa raha hai")
    assert r["red_flags"] == ["chest_pain", "seizure"]
    t = r["trace"]
    assert t["decision"]["source"] == "model+safety_net"
    assert {f["id"]: f["source"] for f in t["red_flags"]} == {"chest_pain": "rules+model", "seizure": "model"}


def test_no_question_when_a_red_flag_is_present(client, student):
    student(output("followup", 0.95))
    r = post(client, "seene mein dard aur saans phool rahi hai", policy="conversational")
    assert r["follow_up_question"] is None and r["care_type"] == "emergency_112"


# ---- deciding and asking --------------------------------------------------------

def test_clear_message_decides_directly_in_the_default_policy(client, student):
    student(output("paramedic", 0.95, "same_day", tags=["fever", "cough"], who="adult"))
    r = post(client, "papa ko do din se bukhar hai aur khansi bhi")
    assert r["follow_up_question"] is None
    assert (r["care_type"], r["urgency"]) == ("paramedic_home_visit", "same_day")
    assert r["matched_caregivers"] and r["trace"]["decision"]["source"] == "model"


def test_followup_class_asks_the_main_question(client, student):
    student(output("followup", 0.95))
    r = post(client, "doctor chahiye")
    assert r["care_type"] is None and r["trace"]["follow_up"]["id"] == "q_main_symptom"


def test_child_fever_without_age_still_asks_the_age(client, student):
    student(output("paramedic", 0.95, tags=["fever"], who="child"))
    r = post(client, "मेरे बेटे को बुखार है")
    assert r["follow_up_question"] == "बच्चे की उम्र कितनी है?"


@pytest.mark.parametrize("message, lang", [("mujhe pizza order karna hai", "hinglish"),
                                           ("Please book a taxi to the airport for me", "en")])
def test_out_of_scope_gets_a_polite_scope_reply(client, student, message, lang):
    student(output("out_of_scope", 0.95, who="unknown"))
    r = post(client, message)
    assert r["follow_up_question"] == followup.question("q_scope", lang).text
    assert r["care_type"] is None and r["urgency"] is None and r["matched_caregivers"] == []
    assert r["trace"]["follow_up"]["id"] == "q_scope"
    assert guards(r)["out_of_scope"] == "fired"


def test_low_confidence_in_the_conversational_policy_asks(client, student):
    # a service request: at high confidence the conversational policy books it directly...
    student(output("nurse", 0.95, tags=["injection"]))
    r = post(client, "ghar pe injection lagwana hai", policy="conversational")
    assert r["care_type"] == "home_nursing" and r["follow_up_question"] is None
    # ...but when the model is unsure it asks what is needed
    student(output("nurse", 0.4, tags=["injection"]))
    r = post(client, "ghar pe injection lagwana hai", policy="conversational")
    assert r["care_type"] is None and r["trace"]["follow_up"]["id"] == "q_main_symptom"
    assert guards(r)["low_confidence"] == "fired" and guards(r)["llm_fallback"] == "pass"


def test_low_confidence_in_the_default_policy_uses_the_rules(client, student):
    student(output("paramedic", 0.4))
    r = post(client, "ghar pe injection lagwana hai")
    assert r["care_type"] == "home_nursing" and r["follow_up_question"] is None
    assert r["trace"]["decision"]["source"] == "safety_net" and guards(r)["low_confidence"] == "fired"


# ---- conversational policy ------------------------------------------------------

def test_conversational_flow_rules_only(client, no_student):
    """The danger check for this complaint first, then how long (naming it), then the
    relative's age; at most three questions."""
    h = [{"role": "user", "content": "papa ko bukhar hai"}]
    r = post(client, "papa ko bukhar hai", policy="conversational")
    assert r["trace"]["follow_up"]["id"] == "q_danger_breathing"  # fever: the breathing check
    assert [o["label"] for o in r["trace"]["follow_up"]["options"]] == ["Haan", "Nahi"]
    r = post(client, "Nahi", h + [turn("q_danger_breathing")], policy="conversational")
    assert r["trace"]["follow_up"]["id"] == "q_duration"
    assert r["follow_up_question"] == "Bukhar kitne din se hai?"
    h2 = h + [turn("q_danger_breathing"), {"role": "user", "content": "Nahi"}, turn("q_duration")]
    r = post(client, "2 din se", h2, policy="conversational")
    assert r["trace"]["follow_up"]["id"] == "q_their_age" and r["trace"]["follow_up"]["asked_so_far"] == 3
    h3 = h2 + [{"role": "user", "content": "2 din se"}, turn("q_their_age")]
    r = post(client, "60 saal ya zyada", h3, policy="conversational")
    assert r["follow_up_question"] is None
    assert (r["care_type"], r["urgency"]) == ("paramedic_home_visit", "same_day")
    s = r["trace"]["structured"]
    assert s["who"] == "elderly" and s["who_label_local"] == "Buzurg" and s["age_years"] == 70
    assert s["duration_days"] == 2
    assert next(c for c in r["trace"]["checks"] if c["id"] == "breathing_difficulty")["status"] == "absent"


def test_conversational_skips_what_is_known(client, no_student):
    r = post(client, "Nahi", [{"role": "user", "content": "dadi ko 3 din se khansi hai"}, turn("q_danger")],
             policy="conversational")
    assert r["follow_up_question"] is None and r["care_type"]  # duration and who already known


def test_conversational_service_request_is_not_quizzed(client, no_student):
    r = post(client, "kal subah sugar test ghar pe", policy="conversational")
    assert r["follow_up_question"] is None and r["care_type"] == "lab_test_home" and r["urgency"] == "scheduled"


@pytest.mark.parametrize("answer", ["Haan", "haan ji", "हाँ", "yes"])
def test_danger_yes_is_an_emergency_without_the_model(client, no_student, answer):
    r = post(client, answer, [{"role": "user", "content": "papa ko bukhar hai"}, turn("q_danger")],
             policy="conversational")
    assert r["care_type"] == "emergency_112" and r["red_flags"] == ["possible_emergency"]
    assert r["matched_caregivers"] == [] and r["trace"]["red_flags"][0]["evidence"] == answer


def test_danger_yes_is_an_emergency_with_the_model(client, student):
    student(output("paramedic", 0.95))  # the model reads the "Haan" as nothing special
    r = post(client, "Haan", [{"role": "user", "content": "papa ko bukhar hai"}, turn("q_danger")],
             policy="conversational")
    assert r["care_type"] == "emergency_112" and r["red_flags"] == ["possible_emergency"]
    assert r["trace"]["decision"]["source"] == "safety_net"


def test_danger_answer_with_a_sign_names_the_sign(client, no_student):
    r = post(client, "haan, saans phool rahi hai", [{"role": "user", "content": "papa ko bukhar hai"},
                                                    turn("q_danger")], policy="conversational")
    assert r["red_flags"] == ["breathlessness"]  # the generic flag gives way to the named one


def test_danger_dont_know_is_unknown(client, no_student):
    r = post(client, "pata nahi", [{"role": "user", "content": "papa ko bukhar hai"}, turn("q_danger")],
             policy="conversational")
    assert r["care_type"] is None and r["trace"]["follow_up"]["id"] == "q_duration"
    assert followup.parse_answer("q_danger", "pata nahi")["danger"] == "unknown"


def test_conversational_unclear_then_default(client, no_student):
    h = [{"role": "user", "content": "help chahiye"}, turn("q_main_symptom"), {"role": "user", "content": "pata nahi"},
         turn("q_danger")]
    r = post(client, "Nahi", h, policy="conversational")
    assert (r["care_type"], r["urgency"]) == ("teleconsultation", "same_day")  # safe default


def test_question_limit(client, student):
    student(output("followup", 0.95))
    h = []
    for qid in ("q_main_symptom", "q_danger", "q_duration"):
        h += [{"role": "user", "content": "pata nahi"}, turn(qid)]
    r = post(client, "pata nahi", h, policy="conversational")
    assert r["follow_up_question"] is None and r["care_type"] == "teleconsultation"


def test_who_answers():
    assert followup.parse_answer("q_who", "Garbhvati mahila") == {"pregnant": True}
    assert followup.parse_answer("q_who", "Baby, 3 mahine se kam") == {"age_years": 0.1}
    assert followup.parse_answer("q_who", "mere papa 72 saal ke hain") == {"age_years": 72}
    assert followup.parse_answer("q_who", "pata nahi") == {}


# ---- urgency floors -------------------------------------------------------------

def test_vulnerable_floor_from_the_model_who(client, student):
    student(output("gp", 0.95, "routine", who="elderly"))  # the words give no age
    r = post(client, "khansi aur zukaam hai")
    assert (r["care_type"], r["urgency"]) == ("teleconsultation", "same_day")
    assert guards(r)["vulnerable_floor"] == "fired" and r["trace"]["decision"]["source"] == "model+safety_net"
    assert r["trace"]["structured"]["who"] == "elderly"


def test_vulnerable_floor_pregnancy_from_the_words(client, student):
    student(output("gp", 0.95, "routine", who="adult"))
    r = post(client, "main 6 mahine pregnant hoon, diet ke baare mein poochna hai")
    assert r["urgency"] == "same_day" and r["trace"]["structured"]["who"] == "pregnant"


def test_rules_urgency_floor(client, student):
    student(output("gp", 0.95, "routine", who="child"))
    r = post(client, "bachche ko 2 din se ulti ho rahi hai, umar 5 saal")
    assert r["urgency"] == "same_day" and guards(r)["urgency_floor"] == "fired"
    assert r["trace"]["decision"]["source"] == "model+safety_net"


def test_lab_is_scheduled_unless_raised(client, student):
    student(output("lab", 0.95, "same_day", tags=["sample_collection"]))
    r = post(client, "cbc aur thyroid test ghar se sample lekar")
    assert (r["care_type"], r["urgency"]) == ("lab_test_home", "scheduled")
    student(output("lab", 0.95, "routine", who="elderly"))  # an older adult's test: booked as asked
    assert post(client, "dadi ka sugar test ghar pe karwana hai")["urgency"] == "scheduled"
    student(output("lab", 0.95, "routine", who="child"))  # the words say 8 months: a baby
    r = post(client, "8 mahine ke bachche ka blood test ghar pe karwana hai")
    assert r["urgency"] == "same_day" and r["trace"]["structured"]["who"] == "infant"


def test_never_emergency_urgency_outside_the_emergency_path(client, student):
    # "immediate" is the urgency head's top class but under the emergency threshold
    student(output("paramedic", 0.95, {"routine": 0.2, "same_day": 0.35, "immediate": 0.45},
                   thresholds={"emergency": 0.5}))
    r = post(client, "papa ko bukhar hai")
    assert r["care_type"] == "paramedic_home_visit" and r["urgency"] == "same_day" and r["red_flags"] == []


# ---- trace: structured, guardrails, safety netting ------------------------------

def test_trace_fields_on_a_decision(client, student):
    student(output("paramedic", 0.95, tags=["fever", "head_injury"], who="adult"))
    r = post(client, "papa ko 3 din se bukhar hai")
    t = r["trace"]
    assert set(guards(r)) == GUARDS and set(guards(r).values()) <= {"pass", "fired"}
    g = t["guardrails"][0]
    assert set(g) >= {"id", "label", "label_local", "status", "note_local"}
    s = t["structured"]
    assert s["symptoms"][0] == {"id": "fever", "label": "Fever", "label_local": "Bukhar"}
    assert s["symptoms"][1]["label"] == "Head injury" and s["duration_days"] == 3 and s["who"] == "adult"
    assert t["safety_net_local"] == ("Agar saans lene mein dikkat, seene mein dard, behoshi, ya bukhar 3 din se "
                                     "zyada rahe, to turant 112 par call karein ya hamein batayein.")
    assert t["decision"]["confidence"] == 0.95


def test_trace_fields_on_other_shapes(client, student):
    student(output("followup", 0.95))
    r = post(client, "help chahiye")
    assert r["trace"]["safety_net_local"] is None and set(guards(r)) == GUARDS and "structured" in r["trace"]
    student(output("emergency", 0.95, "immediate", flags=["seizure"]))
    r = post(client, "help chahiye")
    assert r["trace"]["safety_net_local"] is None and set(guards(r)) == GUARDS


def test_trace_fields_without_the_model(client, no_student):
    r = post(client, "papa ko do din se bukhar hai aur khansi bhi")
    t = r["trace"]
    assert set(guards(r)) == GUARDS and t["decision"]["source"] in ("rules", "model")
    assert [s["id"] for s in t["structured"]["symptoms"]] == ["fever", "cough"]
    assert "112" in t["safety_net_local"] and t["structured"]["duration_days"] == 2
    em = post(client, "Mummy ke seene mein dard hai aur pasina aa raha hai")
    assert guards(em)["safety_net"] == "fired" and em["trace"]["safety_net_local"] is None


def test_safety_net_text_in_three_languages():
    assert text.safety_net("en", fever=True).startswith("If there is trouble breathing")
    assert "112" in text.safety_net("hi") and "बच्चा" in text.safety_net("hi", child=True)
    for lang in ("en", "hi", "hinglish"):
        assert not text.has_banned(text.safety_net(lang, fever=True, child=True))


def test_reasoning_from_model_tags_when_the_lexicon_knows_no_word(client, student):
    student(output("paramedic", 0.95, tags=["fever"]))
    r = post(client, "tabiyat bigdi hui hai, ghar pe koi dekh le")
    assert r["care_type"] == "paramedic_home_visit"
    assert "unclear" not in r["reasoning"].lower() and "not clear" not in r["reasoning"].lower()
    student(output("paramedic", 0.95))
    r = post(client, "tabiyat bigdi hui hai, ghar pe koi dekh le")
    assert r["reasoning"].startswith("Based on your message")


def test_health_reports_the_model(client, student):
    student(output())
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["model"] == "student (MuRIL)"
    assert h["model_test_accuracy"] == 0.97 and h["student"]["trained_at"] == FakeStudent.meta["trained_at"]
    assert {"caregivers_source", "caregivers", "model_trained_at", "llm_fallback"} <= set(h)


def test_model_failure_falls_back_to_rules(client, monkeypatch):
    class Broken:
        def predict(self, text, history=None):
            raise RuntimeError("onnx went away")
    monkeypatch.setattr("app.pipeline.get_student", lambda: Broken())
    r = post(client, "papa ko do din se bukhar hai aur khansi bhi")
    assert r["care_type"] == "paramedic_home_visit"
    assert (r["trace"].get("model") or {}).get("name") != "MuRIL (fine-tuned)"


# ---- Claude second opinion -------------------------------------------------------

def opinion(care=None, urgency=None, flags=()):
    return llm_fallback.LLMOpinion(care=care, urgency=urgency, red_flags=list(flags), reasoning="r",
                                   model="claude-opus-5-5", latency_ms=5.0)


def test_llm_fallback_off_without_the_env_var(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setattr(llm_fallback, "_client", lambda: pytest.fail("the client must not be built"))
    assert not llm_fallback.enabled() and llm_fallback.ask("papa ko bukhar hai") is None
    monkeypatch.setenv("CC_LLM_FALLBACK", "on")
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert not llm_fallback.enabled() and llm_fallback.ask("papa ko bukhar hai") is None


def test_llm_not_called_when_off(client, student, monkeypatch):
    called = []
    monkeypatch.setattr(llm_fallback, "_client", lambda: called.append(1))
    student(output("paramedic", 0.4))
    r = post(client, "papa ko bukhar hai")
    assert called == [] and guards(r)["llm_fallback"] == "pass" and "llm" not in r["trace"]


def test_llm_opinion_is_used_when_the_model_is_unsure(client, student, monkeypatch):
    seen = []
    monkeypatch.setattr("app.pipeline.llm_fallback.ask", lambda t, h=None: seen.append(t) or opinion("lab", "routine"))
    student(output("paramedic", 0.4))
    r = post(client, "sugar ka test karwana hai")
    assert seen == ["sugar ka test karwana hai"]
    assert (r["care_type"], r["urgency"]) == ("lab_test_home", "scheduled")
    assert r["trace"]["decision"]["source"] == "llm" and guards(r)["llm_fallback"] == "fired"
    assert r["trace"]["llm"]["care_type"] == "lab_test_home"


def test_llm_unclear_asks(client, student, monkeypatch):
    monkeypatch.setattr("app.pipeline.llm_fallback.ask", lambda t, h=None: opinion(None, None))
    student(output("paramedic", 0.4))
    assert post(client, "kuch karna hai")["trace"]["follow_up"]["id"] == "q_main_symptom"


def test_llm_can_add_an_emergency(client, student, monkeypatch):
    monkeypatch.setattr("app.pipeline.llm_fallback.ask", lambda t, h=None: opinion("emergency", "immediate", ["seizure"]))
    student(output("paramedic", 0.4))
    r = post(client, "papa ko kuch ho raha hai")
    assert r["care_type"] == "emergency_112" and r["red_flags"] == ["seizure"]
    assert r["trace"]["decision"]["source"] == "llm" and r["trace"]["red_flags"][0]["source"] == "llm"


@pytest.mark.parametrize("message, out", [
    ("help chahiye", output("emergency", 0.5, "immediate", flags=["chest_pain"])),  # the model's, low band
    ("papa ko severe chest pain hai saans nahi aa rahi", output("paramedic", 0.4)),  # the rules'
])
def test_llm_never_removes_an_emergency(client, student, monkeypatch, message, out):
    calls = []
    monkeypatch.setattr("app.pipeline.llm_fallback.ask", lambda t, h=None: calls.append(t) or opinion("nurse", "routine"))
    student(out)
    r = post(client, message)
    assert r["care_type"] == "emergency_112" and r["urgency"] == "emergency" and r["red_flags"]
    assert calls == []  # not even asked


def test_llm_ask_request_and_parsing(monkeypatch):
    monkeypatch.setenv("CC_LLM_FALLBACK", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    sent = {}

    def answer(stop_reason="end_turn", body='{"care_type": "home_nursing", "urgency": "same_day", '
                                            '"red_flags": [], "reasoning": "A nursing procedure."}'):
        def create(**kw):
            sent.update(kw)
            return SimpleNamespace(stop_reason=stop_reason, stop_details=None,
                                   content=[SimpleNamespace(type="text", text=body)])
        return SimpleNamespace(messages=SimpleNamespace(create=create))

    monkeypatch.setattr(llm_fallback, "_client", lambda: answer())
    o = llm_fallback.ask("ghar pe injection", [("user", "namaste"), ("assistant", "Kya chahiye?")])
    assert (o.care, o.urgency, o.red_flags) == ("nurse", "same_day", [])
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"]["effort"] == "low" and sent["output_config"]["format"]["type"] == "json_schema"
    assert "ghar pe injection" in sent["messages"][0]["content"] and "namaste" in sent["messages"][0]["content"]
    assert "sanocare" not in sent["system"].lower()
    monkeypatch.setattr(llm_fallback, "_client", lambda: answer(stop_reason="refusal"))
    assert llm_fallback.ask("x") is None
    monkeypatch.setattr(llm_fallback, "_client", lambda: answer(body="not json"))
    assert llm_fallback.ask("x") is None
    monkeypatch.setattr(llm_fallback, "_client", lambda: answer(body='{"care_type": "pizza", "urgency": null, '
                                                                    '"red_flags": [], "reasoning": ""}'))
    assert llm_fallback.ask("x") is None

    def boom(**kw):
        raise TimeoutError("slow")
    monkeypatch.setattr(llm_fallback, "_client", lambda: SimpleNamespace(messages=SimpleNamespace(create=boom)))
    assert llm_fallback.ask("x") is None
    monkeypatch.setenv("CC_LLM_MODEL", "claude-sonnet-5-5")
    monkeypatch.setattr(llm_fallback, "_client", lambda: answer())
    llm_fallback.ask("x")
    assert sent["model"] == "claude-sonnet-5-5"


def test_danger_check_fits_the_complaint(client, no_student):
    cases = {"mummy ko subah se ulti aur dast ho rahe hain": "q_danger_dehydration",
             "pet mein dard hai": "q_danger_abdomen", "sar mein bahut dard hai": "q_danger_stroke",
             "mann bahut udaas rehta hai": "q_danger_mind"}
    for text_, qid in cases.items():
        r = post(client, text_, policy="conversational")
        assert r["trace"]["follow_up"]["id"] == qid, (text_, r["trace"]["follow_up"])
    # a "Haan" raises that check's red flag, not a generic one
    r = post(client, "Haan", [{"role": "user", "content": "sar mein bahut dard hai"}, turn("q_danger_stroke")],
             policy="conversational")
    assert r["care_type"] == "emergency_112" and r["red_flags"] == ["stroke_symptoms"]

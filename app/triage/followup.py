"""Follow-up questions: a fixed bank in three languages, the policies that pick the next
one, and answer parsing.

Policies:
- minimal (default, used by the organisers' scorer): ask only when the answer is needed
  to decide (what the problem is, a child's age, sometimes how long).
- safety: minimal plus a breathing check for fever and cough.
- conversational (web and app): a short check-up of at most MAX_FOLLOWUPS questions. For a
  symptom: danger signs first, then how long, then who it is for; a service request
  (injection, dressing, lab test) is booked without them."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import FOLLOWUP_POLICY, MAX_FOLLOWUPS
from ..nlp.extract import Extraction, extract
from ..nlp.normalize import to_roman
from .rules import Decision

YES = {"haan", "ha", "haa", "han", "hanji", "haanji", "ji", "yes", "y", "yeah", "yep", "sahi", "bilkul"}
NO = {"nahi", "nahin", "nai", "nhi", "na", "no", "n", "nope", "nahee"}
UNKNOWN = {"pata nahi", "pta nahi", "maloom nahi", "don't know", "dont know", "not sure", "unknown", "pata nahin"}
BREATHING_ECHO = re.compile(r"\b(ho rahi|ho raha|ho rahe|hoti|thodi|thoda|a little|little bit|having|kabhi kabhi"
                            r"|he is|she is|phool|fool)\b")
NEGATED = re.compile(r"\b(nahi|nahin|nhi|no|not|na)\b")
DURATION_MARKER = re.compile(r"\b(se|since|from|pehle|ago|for|gaye|hue|kal|aaj|subah|raat|last|pichle|pichhle)\b")

QUESTIONS: dict[str, dict] = {
    "q_main_symptom": {
        "kind": "free_text",
        "text": {
            "en": "Happy to help. Who is this for, and what is needed: a symptom such as fever or pain, "
                  "nursing at home (injection, dressing), a lab test, or a doctor consult?",
            "hinglish": "Zaroor madad karenge. Kiske liye hai, aur kya chahiye: koi taklif jaise bukhar ya dard, "
                        "ghar pe nursing (injection, dressing), lab test, ya doctor se baat?",
            "hi": "ज़रूर मदद करेंगे। किसके लिए है, और क्या चाहिए: कोई तकलीफ़ जैसे बुखार या दर्द, "
                  "घर पर नर्सिंग (इंजेक्शन, ड्रेसिंग), लैब टेस्ट, या डॉक्टर से बात?",
        },
        "options": [
            ("fever", {"en": "Fever", "hinglish": "Bukhar", "hi": "बुखार"}),
            ("pain", {"en": "Pain", "hinglish": "Dard", "hi": "दर्द"}),
            ("breathing", {"en": "Breathing trouble", "hinglish": "Saans ki dikkat", "hi": "सांस की दिक्कत"}),
            ("nursing", {"en": "Injection or dressing", "hinglish": "Injection / dressing", "hi": "इंजेक्शन / ड्रेसिंग"}),
            ("lab", {"en": "Lab test at home", "hinglish": "Ghar pe lab test", "hi": "घर पर लैब टेस्ट"}),
            ("doctor", {"en": "Talk to a doctor", "hinglish": "Doctor se baat", "hi": "डॉक्टर से बात"}),
        ],
    },
    "q_age": {
        "kind": "choice",
        "text": {
            "en": "How old is the child?",
            "hinglish": "Bachche ki umar kitni hai?",
            "hi": "बच्चे की उम्र कितनी है?",
        },
        "options": [
            ("young_infant", {"en": "Under 3 months", "hinglish": "3 mahine se kam", "hi": "3 महीने से कम"}),
            ("infant", {"en": "3 to 12 months", "hinglish": "3 se 12 mahine", "hi": "3 से 12 महीने"}),
            ("child", {"en": "1 to 12 years", "hinglish": "1 se 12 saal", "hi": "1 से 12 साल"}),
            ("adult", {"en": "13 or older", "hinglish": "13 saal ya zyada", "hi": "13 साल या ज़्यादा"}),
        ],
    },
    "q_duration": {
        "kind": "choice",
        "text": {
            "en": "Since when has this been happening?",
            "hinglish": "Kitne din se ho raha hai?",
            "hi": "कितने दिन से हो रहा है?",
        },
        "options": [
            ("today", {"en": "Since today", "hinglish": "Aaj se", "hi": "आज से"}),
            ("2_3_days", {"en": "2-3 days", "hinglish": "2-3 din", "hi": "2-3 दिन"}),
            ("week", {"en": "More than a week", "hinglish": "1 hafte se zyada", "hi": "1 हफ़्ते से ज़्यादा"}),
            ("month", {"en": "More than a month", "hinglish": "1 mahine se zyada", "hi": "1 महीने से ज़्यादा"}),
        ],
    },
    "q_breathing": {
        "kind": "yes_no",
        "text": {
            "en": "Is there any difficulty in breathing?",
            "hinglish": "Kya saans lene mein dikkat ho rahi hai?",
            "hi": "क्या सांस लेने में दिक्कत हो रही है?",
        },
        "options": [
            ("yes", {"en": "Yes", "hinglish": "Haan", "hi": "हाँ"}),
            ("no", {"en": "No", "hinglish": "Nahi", "hi": "नहीं"}),
            ("unknown", {"en": "Not sure", "hinglish": "Pata nahi", "hi": "पता नहीं"}),
        ],
    },
    # the same wording the fine-tuned model saw in its multi-turn training examples
    "q_danger": {
        "kind": "yes_no",
        "text": {
            "en": "Is there any trouble breathing, chest pain, fainting or heavy bleeding?",
            "hinglish": "Kya saans lene mein dikkat, seene mein dard, behoshi ya bahut tez khoon behna jaisa kuch hai?",
            "hi": "क्या सांस लेने में दिक्कत, सीने में दर्द, बेहोशी या बहुत खून बहना जैसा कुछ है?",
        },
        "options": [
            ("yes", {"en": "Yes", "hinglish": "Haan", "hi": "हाँ"}),
            ("no", {"en": "No", "hinglish": "Nahi", "hi": "नहीं"}),
        ],
    },
    "q_who": {
        "kind": "choice",
        "text": {
            "en": "Who is this for, and how old are they?",
            "hinglish": "Yeh kiske liye hai, aur unki umar kitni hai?",
            "hi": "यह किसके लिए है, और उनकी उम्र कितनी है?",
        },
        "options": [
            ("adult", {"en": "Adult (13 to 59)", "hinglish": "Bade (13 se 59 saal)", "hi": "बड़े (13 से 59 साल)"}),
            ("elderly", {"en": "60 or older", "hinglish": "60 saal ya zyada", "hi": "60 साल या ज़्यादा"}),
            ("child", {"en": "Child (1 to 12)", "hinglish": "Bachcha (1 se 12 saal)", "hi": "बच्चा (1 से 12 साल)"}),
            ("infant", {"en": "Baby, 3 to 12 months", "hinglish": "Baby, 3 se 12 mahine", "hi": "शिशु, 3 से 12 महीने"}),
            ("young_infant", {"en": "Baby under 3 months", "hinglish": "Baby, 3 mahine se kam",
                              "hi": "शिशु, 3 महीने से कम"}),
            ("pregnant", {"en": "Pregnant woman", "hinglish": "Garbhvati mahila", "hi": "गर्भवती महिला"}),
        ],
    },
    # not a question about symptoms: the polite reply when the message is not about health care
    "q_scope": {
        "kind": "free_text",
        "text": {
            "en": "We can only help with health care at home: a doctor call, a home visit, nursing or a "
                  "lab test. Is someone unwell?",
            "hinglish": "Hum sirf ghar pe health care mein madad karte hain: doctor se baat, ghar pe check-up, "
                        "nursing ya lab test. Kya koi beemar hai?",
            "hi": "हम सिर्फ़ घर पर स्वास्थ्य देखभाल में मदद करते हैं: डॉक्टर से बात, घर पर जाँच, "
                  "नर्सिंग या लैब टेस्ट। क्या कोई बीमार है?",
        },
        "options": [
            ("fever", {"en": "Fever", "hinglish": "Bukhar", "hi": "बुखार"}),
            ("pain", {"en": "Pain", "hinglish": "Dard", "hi": "दर्द"}),
            ("nursing", {"en": "Injection or dressing", "hinglish": "Injection / dressing", "hi": "इंजेक्शन / ड्रेसिंग"}),
            ("lab", {"en": "Lab test at home", "hinglish": "Ghar pe lab test", "hi": "घर पर लैब टेस्ट"}),
            ("doctor", {"en": "Talk to a doctor", "hinglish": "Doctor se baat", "hi": "डॉक्टर से बात"}),
        ],
    },
}
DURATION_VALUES = {"today": 0.0, "2_3_days": 2.0, "week": 7.0, "month": 30.0}
AGE_VALUES = {"young_infant": 0.1, "infant": 0.5, "child": 5.0, "adult": 30.0}
WHO_VALUES = {"adult": {"age_years": 30.0}, "elderly": {"age_years": 70.0}, "child": {"age_years": 5.0},
              "infant": {"age_years": 0.5}, "young_infant": {"age_years": 0.1}, "pregnant": {"pregnant": True}}


@dataclass
class Question:
    id: str
    text: str
    kind: str
    options: list[dict]


def question(qid: str, language: str) -> Question:
    q = QUESTIONS[qid]
    lang = language if language in ("en", "hi", "hinglish") else "en"
    return Question(id=qid, text=q["text"][lang], kind=q["kind"],
                    options=[{"value": v, "label": labels[lang]} for v, labels in q["options"]])


# other apps' wording of the same questions ("How old is she?", "Kab se hai?")
QUESTION_WORDS = {
    "q_age": re.compile(r"\b(how old|age|umar|umr|kitne saal (ka|ki|ke))\b|उम्र|उमर"),
    "q_duration": re.compile(r"\b(how long|since when|how many days|kab se|kitne din|kitne dino|kitne samay)\b"
                             r"|कब से|कितने दिन"),
    "q_breathing": re.compile(r"\b(saans|sans|breath\w*)\b|सांस|साँस"),
}
# a question about something else: "Kitne saal se sugar hai?", "How long has he been diabetic?",
# or about the past: "Ye saans rone ki baat pehle bhi hui?" (a "haan" there is not breathing trouble now)
OTHER_SUBJECT = re.compile(r"\b(sugar|diabet\w*|bp|blood pressure|dawai|dawa|medicine\w*|tablet\w*|goli|insulin"
                           r"|treatment|ilaj|operation|pregnan\w*|pehle|pahle|before|kabhi|history|pichle|pichhle)\b"
                           r"|दवा|शुगर|पहले")


def identify(text: str, question_id: str | None = None, keywords: bool = True) -> str | None:
    """Which bank question an assistant turn was: by id, else by exact text, else (for turns
    known to come from the assistant) by its words, when exactly one of our questions fits."""
    if question_id in QUESTIONS:
        return question_id
    norm = (text or "").strip().lower()
    for qid, q in QUESTIONS.items():
        if any(norm == t.lower() for t in q["text"].values()):
            return qid
    if keywords and norm.endswith("?") and not OTHER_SUBJECT.search(norm):
        hits = [qid for qid, words in QUESTION_WORDS.items() if words.search(norm)]
        if len(hits) == 1:  # "Kab se hai aur umar kya hai?" asks two things: read the answer as text
            return hits[0]
    return None


def _option_value(qid: str, answer: str) -> str | None:
    norm = to_roman(answer).strip(" .!?").lower()
    raw = (answer or "").strip(" .!?").lower()
    for value, labels in QUESTIONS[qid]["options"]:
        if norm == value or any(raw == lbl.lower() or norm == to_roman(lbl).lower() for lbl in labels.values()):
            return value
    return None


def option_value(qid: str, answer: str) -> str | None:
    """The option an answer picked (by value or by its label in any language), if any."""
    return _option_value(qid, answer) if qid in QUESTIONS else None


def yes_no(answer: str) -> str | None:
    norm = re.sub(r"[^a-z ]", " ", to_roman(answer).lower()).strip()
    if any(norm.startswith(u) for u in UNKNOWN):
        return "unknown"
    words = norm.split()
    if not words:
        return None
    if words[0] in YES:
        return "yes"
    if words[0] in NO:
        return "no"
    return None


def parse_answer(qid: str, answer: str) -> dict:
    """Facts from an answer to one of our questions."""
    value = _option_value(qid, answer)
    if qid == "q_breathing":
        v = value or yes_no(answer)
        if v is None and BREATHING_ECHO.search(to_roman(answer).lower()) and not NEGATED.search(to_roman(answer).lower()):
            v = "yes"  # "ho rahi hai", "thodi si", "a little"
        return {"breathing": {"yes": "present", "no": "absent"}.get(v or "", "not_reported")}
    if qid == "q_duration":
        if value in DURATION_VALUES:
            return {"duration_days": DURATION_VALUES[value]}
        ex = extract(answer)
        return {"duration_days": ex.duration_days} if ex.duration_days is not None else {}
    if qid == "q_age":
        if value in AGE_VALUES:
            return {"age_years": AGE_VALUES[value]}
        ex = extract(answer)
        if ex.age_years is not None:
            return {"age_years": ex.age_years}
        # "2 mahine" read as a duration is the age here; "2 din se" or "kal se" is still a duration
        if ex.duration_days is not None and not DURATION_MARKER.search(to_roman(answer).lower()):
            return {"age_years": ex.duration_days / 365}
        bare = re.fullmatch(r"\s*(\d{1,3})\s*", to_roman(answer))
        return {"age_years": float(bare.group(1))} if bare and int(bare.group(1)) <= 120 else {}
    if qid == "q_danger":
        # "Haan" sends the conversation to the emergency path; "pata nahi" stays unknown
        v = value or yes_no(answer)
        return {"danger": {"yes": "present", "no": "absent"}.get(v or "", "unknown")}
    if qid == "q_who":
        if value in WHO_VALUES:
            return dict(WHO_VALUES[value])
        ex = extract(answer)
        if ex.pregnant:
            return {"pregnant": True}
        if ex.age_years is not None:
            return {"age_years": ex.age_years}
        bare = re.fullmatch(r"\s*(\d{1,3})\s*", to_roman(answer))
        return {"age_years": float(bare.group(1))} if bare and int(bare.group(1)) <= 120 else {}
    return {}


def _who_known(ex: Extraction, who: str | None) -> bool:
    """Enough is known about who the patient is: an age, a pregnancy, an older adult (from
    "dadi", "buzurg"), or the model is sure it is an older adult or a pregnancy."""
    return (ex.age_years is not None or bool(ex.pregnant) or ex.age_group == "older_adult"
            or who in ("elderly", "pregnant"))


def _conversational(ex: Extraction, decision: Decision, asked: list[str], service: bool,
                    who: str | None) -> str | None:
    for need, qid in (("scope", "q_scope"), ("main_symptom", "q_main_symptom")):
        if need in decision.needs:
            if qid not in asked:
                return qid
            # asked and still unclear: one danger check, then the safe default
            return "q_danger" if need == "main_symptom" and "q_danger" not in asked else None
    if service:  # injection, dressing, lab test: booked as asked (a child's fever still needs the age)
        return "q_age" if "age" in decision.needs and "q_age" not in asked else None
    if "q_danger" not in asked:
        return "q_danger"
    if "age" in decision.needs and "q_age" not in asked:
        return "q_age"
    if ex.duration_days is None and "q_duration" not in asked:
        return "q_duration"
    if not _who_known(ex, who) and "q_age" not in asked and "q_who" not in asked:
        child = ex.age_group in ("infant", "child") or ex.relation in ("child", "infant") or who in ("child", "infant")
        return "q_age" if child else "q_who"
    return None


def choose(ex: Extraction, decision: Decision, asked: list[str], policy: str | None = None,
           service: bool = False, who: str | None = None) -> str | None:
    """Next question id, or None to decide now. Never asks when a red flag is present.
    `service`: the request is a service (nursing, lab test), not a complaint. `who`: the
    fine-tuned model's guess of who the patient is, if it ran."""
    policy = policy or FOLLOWUP_POLICY
    if ex.red_flags or len(asked) >= MAX_FOLLOWUPS:
        return None
    if policy == "conversational":
        return _conversational(ex, decision, asked, service, who)
    for need, qid in (("scope", "q_scope"), ("main_symptom", "q_main_symptom"), ("age", "q_age"),
                      ("duration", "q_duration")):
        if need in decision.needs and qid not in asked:
            return qid
    if policy == "safety" and "q_breathing" not in asked and "breathing_difficulty" not in ex.negated_flags:
        if any(h.entry.meta.get("respiratory") for h in ex.symptoms) or (
                "fever" in ex.symptom_ids() and ex.age_group in ("infant", "child", "older_adult")):
            return "q_breathing"
    return None

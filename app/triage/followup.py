"""Follow-up questions: a fixed bank in three languages, a policy that asks only
when the answer can change the decision, and answer parsing."""
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
            "en": "What problem are they having? For example fever, pain, breathing trouble, vomiting or an injury.",
            "hinglish": "Unhe kya taklif ho rahi hai? Jaise bukhar, dard, saans ki dikkat, ulti ya chot.",
            "hi": "उन्हें क्या तकलीफ़ हो रही है? जैसे बुखार, दर्द, सांस की दिक्कत, उल्टी या चोट।",
        },
        "options": [
            ("fever", {"en": "Fever", "hinglish": "Bukhar", "hi": "बुखार"}),
            ("pain", {"en": "Pain", "hinglish": "Dard", "hi": "दर्द"}),
            ("breathing", {"en": "Breathing trouble", "hinglish": "Saans ki dikkat", "hi": "सांस की दिक्कत"}),
            ("vomiting", {"en": "Vomiting / loose motions", "hinglish": "Ulti / dast", "hi": "उल्टी / दस्त"}),
            ("injury", {"en": "Injury", "hinglish": "Chot", "hi": "चोट"}),
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
}
DURATION_VALUES = {"today": 0.0, "2_3_days": 2.0, "week": 7.0, "month": 30.0}
AGE_VALUES = {"young_infant": 0.1, "infant": 0.5, "child": 5.0, "adult": 30.0}


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
# a question about something else: "Kitne saal se sugar hai?", "How long has he been diabetic?"
OTHER_SUBJECT = re.compile(r"\b(sugar|diabet\w*|bp|blood pressure|dawai|dawa|medicine\w*|tablet\w*|goli|insulin"
                           r"|treatment|ilaj|operation|pregnan\w*)\b|दवा|शुगर")


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
    return {}


def choose(ex: Extraction, decision: Decision, asked: list[str], policy: str | None = None) -> str | None:
    """Next question id, or None to decide now. Never asks when a red flag is present."""
    policy = policy or FOLLOWUP_POLICY
    if ex.red_flags or len(asked) >= MAX_FOLLOWUPS:
        return None
    for need, qid in (("main_symptom", "q_main_symptom"), ("age", "q_age"), ("duration", "q_duration")):
        if need in decision.needs and qid not in asked:
            return qid
    if policy == "safety" and "q_breathing" not in asked and "breathing_difficulty" not in ex.negated_flags:
        if any(h.entry.meta.get("respiratory") for h in ex.symptoms) or (
                "fever" in ex.symptom_ids() and ex.age_group in ("infant", "child", "older_adult")):
            return "q_breathing"
    return None

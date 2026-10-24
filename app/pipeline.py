"""One request in, one decision out: read the conversation, check red flags,
extract facts, decide (or ask), match caregivers, explain.

Model-first when the fine-tuned model (app/triage/student.py) is loaded:
- the lexicon still extracts facts (duration, age, answers) and its red-flag rules are the
  safety net: they can only escalate;
- emergency if the rules find a red flag OR the model says so; otherwise the model's care
  type, with Claude as a second opinion when the model is unsure (app/triage/llm_fallback.py);
- urgency is the model's, never below the rules' and at least same day for a baby, an older
  adult or a pregnancy.
Without the model (missing file, CC_STUDENT=off, CI) the rules + the older TF-IDF model
decide exactly as before."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import config
from .config import RED_FLAG_INTERNAL, VERSION, api_care, api_urgency
from .matching.ranker import rank
from .nlp.extract import Extraction, extract
from .nlp.lexicon import get_lexicon
from .nlp.normalize import to_roman
from .schemas import MatchedCaregiver, TriageRequest, TriageResponse, TriageResponseWithTrace
from .config import URGENCY_ORDER, urgency_rank
from .triage import followup, llm_fallback, text
from .triage.model import FOLLOWUP, care_urgency, fuse, get_model
from .triage.rules import Decision, decide
from .triage.student import StudentOutput, get_student

log = logging.getLogger(__name__)

USER_ROLES = {"user", "patient", "human", "customer", "client"}
ASSISTANT_ROLES = {"assistant", "bot", "system", "agent", "ai", "app", "model", "chatbot"}
# read via parse_answer, not as free text
STRUCTURED_ANSWERS = {"q_age", "q_duration", "q_breathing", "q_danger", "q_who"}
CARE_KEYS = ("paramedic", "nurse", "lab", "gp", "specialist")  # a decision (not emergency, not "ask")
OUT_OF_SCOPE = "out_of_scope"
VULNERABLE = ("infant", "elderly", "pregnant")

ASK_REASON = {
    "q_main_symptom": {"en": "The main problem is not clear yet, so one question is needed before routing.",
                       "hinglish": "Abhi saaf nahi hai ki taklif kya hai, isliye ek sawaal.",
                       "hi": "अभी साफ़ नहीं है कि तकलीफ़ क्या है, इसलिए एक सवाल।"},
    "q_age": {"en": "Fever in a child: the child's age decides how urgent this is.",
              "hinglish": "Bachche ko bukhar hai: umar se tay hoga ki kitni jaldi chahiye.",
              "hi": "बच्चे को बुखार है: उम्र से तय होगा कि कितनी जल्दी चाहिए।"},
    "q_duration": {"en": "How long this has lasted decides the care type.",
                   "hinglish": "Kitne din se hai, us se care tay hogi.",
                   "hi": "कितने दिन से है, उससे देखभाल तय होगी।"},
    "q_breathing": {"en": "Checking for breathing difficulty before deciding.",
                    "hinglish": "Faisle se pehle saans ki dikkat check kar rahe hain.",
                    "hi": "फ़ैसले से पहले सांस की दिक्कत जाँच रहे हैं।"},
    "q_danger": {"en": "Checking for danger signs before deciding.",
                 "hinglish": "Faisle se pehle khatre ke lakshan check kar rahe hain.",
                 "hi": "फ़ैसले से पहले ख़तरे के लक्षण जाँच रहे हैं।"},
    "q_who": {"en": "Who the care is for, and their age, decides how soon someone should come.",
              "hinglish": "Kiske liye hai aur umar kya hai, us se tay hoga ki kitni jaldi chahiye.",
              "hi": "किसके लिए है और उम्र क्या है, उससे तय होगा कि कितनी जल्दी चाहिए।"},
    "q_scope": {"en": "This does not look like a home health care request.",
                "hinglish": "Yeh ghar pe health care ki request nahi lagti.",
                "hi": "यह घर पर स्वास्थ्य देखभाल का अनुरोध नहीं लगता।"},
}


@dataclass
class Turn:
    role: str
    text: str
    question_id: str | None = None


def read_history(items: list[Any]) -> list[Turn]:
    """Accepts strings, {"role", "content"}, {"question", "answer"} and similar."""
    turns: list[Turn] = []
    for item in items or []:
        if isinstance(item, str):
            # a bare string may be the family's own words ("umar 65 hai ... kya karein?"):
            # only our exact question text makes it an assistant turn
            qid = followup.identify(item, keywords=False)
            turns.append(Turn("assistant" if qid else "user", item, qid))
            continue
        if not isinstance(item, dict):
            continue
        if "question" in item or "answer" in item:
            if item.get("question"):
                q = str(item["question"])
                turns.append(Turn("assistant", q, followup.identify(q, item.get("question_id"))))
            if item.get("answer") is not None:
                turns.append(Turn("user", str(item["answer"])))
            continue
        role = str(item.get("role") or item.get("speaker") or item.get("sender") or item.get("from") or "user").lower()
        content = item.get("content") or item.get("text") or item.get("message") or item.get("utterance") or ""
        if isinstance(content, list):  # [{"type": "text", "text": ...}]
            content = " ".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in content)
        content = str(content)
        if role in ASSISTANT_ROLES:
            turns.append(Turn("assistant", content, followup.identify(content, item.get("question_id"))))
        else:
            turns.append(Turn("user", content))
    return turns


def _checks(ex: Extraction, breathing: str, flag_ids: list[str], language: str) -> list[dict]:
    lex_by_id = ex_entries(ex)
    out = []
    respiratory = any(h.entry.meta.get("respiratory") for h in ex.symptoms) or "fever" in ex.symptom_ids()
    if respiratory and "breathing_difficulty" not in flag_ids:
        e = lex_by_id["breathing_difficulty"]
        out.append({"id": e.id, "label": e.label, "label_local": e.label_for(language), "status": breathing})
    for fid in flag_ids:
        e = lex_by_id.get(fid)
        if e:
            out.append({"id": fid, "label": e.label, "label_local": e.label_for(language), "status": "present"})
    for fid in sorted(ex.negated_flags):
        e = lex_by_id.get(fid)
        if e and fid not in flag_ids and not (fid == "breathing_difficulty" and respiratory):
            out.append({"id": fid, "label": e.label, "label_local": e.label_for(language), "status": "absent"})
    return out


def ex_entries(ex: Extraction) -> dict:
    from .nlp.lexicon import get_lexicon
    return get_lexicon().by_id


def _understood(ex: Extraction, language: str) -> dict:
    def item(h):
        return {"id": h.id, "label": h.entry.label, "label_local": h.entry.label_for(language)}

    return {
        "patient": {"relation": ex.relation, "relation_label": ex.relation_label,
                    "age_years": None if ex.age_years is None else round(ex.age_years, 2),
                    "age_group": ex.age_group, "pregnant": ex.pregnant},
        "symptoms": [item(h) for h in ex.symptoms],
        "duration_days": ex.duration_days,
        "duration_label": text.duration_label(ex.duration_days, "en"),
        "services": [item(h) for h in ex.services],
        "severity": sorted(ex.severity),
    }


def _decision_trace(care: str | None, urgency: str | None, d: Decision, language: str,
                    source: str = "rules") -> dict:
    lang = text.lang_of(language)
    return {
        "care_type": api_care(care), "urgency": api_urgency(urgency),
        "care_label": text.CARE_LABELS[care]["en"] if care else None,
        "care_label_local": text.CARE_LABELS[care][lang] if care else None,
        "urgency_label": text.URGENCY_LABELS[urgency]["en"] if urgency else None,
        "urgency_label_local": text.URGENCY_LABELS[urgency][lang] if urgency else None,
        "confidence": round(d.confidence, 2), "source": source, "rule": d.rule,
        "specialty": d.specialty,
    }


def _apply_model(ex: Extraction, d: Decision, combined: str) -> tuple[Decision, bool, str, dict]:
    """Run the learned model on every request and combine it with the rules' decision.
    Returns (decision, model_says_emergency, source, model_probabilities)."""
    model = get_model()
    if model is None:
        return d, False, "rules", {}
    s = model.settings
    probs = model.probs(combined, ex)
    if probs.get("emergency", 0.0) >= s["emergency_threshold"]:
        return d, True, "model", probs
    care, p = fuse(probs, d.care, s)
    if care == FOLLOWUP:  # not enough to decide: ask what is needed
        needs = list(dict.fromkeys(d.needs + ["main_symptom"]))
        return Decision(None, None, round(p, 2), d.rule + "+model", needs=needs), False, "model", probs
    urgency = care_urgency(care, d.urgency)
    return (Decision(care, urgency, round(p, 2), d.rule + "+model", needs=[n for n in d.needs if n != "main_symptom"],
                     specialty=d.specialty if care in (d.care, "gp") else None), False, "model", probs)


# ---- model-first route (the fine-tuned model is loaded) ----------------------

@dataclass
class Route:
    decision: Decision  # care None: ask `qid`, or (no question left) the safe default
    source: str  # model | model+safety_net | safety_net | llm (trace.decision.source)
    qid: str | None = None
    emergency: list[str] | None = None  # our flag ids when this is an emergency
    flag_source: dict[str, str] = field(default_factory=dict)  # flag id -> rules | model | rules+model | llm
    llm: llm_fallback.LLMOpinion | None = None


def _merge_flags(flags: list[str]) -> list[str]:
    """Flags in order, once each; "possible_emergency" / "other_emergency" only when no
    specific sign is named."""
    flags = list(dict.fromkeys(flags))
    specific = [f for f in flags if f not in config.GENERIC_FLAGS]
    return specific or flags


def _is_service(ex: Extraction, care: str | None) -> bool:
    """A request for a service (nursing procedure, lab test, a check-up asked for) rather than
    a complaint: no danger or duration questions."""
    return care in ("nurse", "lab") or (bool(ex.services) and not ex.symptoms)


def _model_emergency(so: StudentOutput) -> bool:
    # the care head's emergency class and the red-flag heads; the urgency head is not used here
    # (it is not trained on follow-up messages, so its "immediate" is noise on them)
    return so.says_emergency


def _model_first(so: StudentOutput, ex: Extraction, rule_flags: list[str], asked: list[str], policy: str | None,
                 interactive: bool, user_text: str, history: list[tuple[str, str]], who: str,
                 fired: set[str]) -> Route:
    """The decision when the fine-tuned model is loaded. `fired` collects the guardrails
    that changed or decided something."""
    # 1) emergency: the rules' red flags (the safety net) or the model
    model_em = _model_emergency(so)
    if rule_flags or model_em:
        flags = list(rule_flags)
        source_of = {f: "rules" for f in rule_flags}
        if rule_flags:
            fired.add("safety_net")
        if model_em:
            fired.add("model_emergency")
            for f in so.flags_on():
                fid = RED_FLAG_INTERNAL.get(f, f)
                source_of[fid] = "rules+model" if fid in source_of else "model"
                flags.append(fid)
            if not flags:  # the care or urgency head alone: no particular sign named
                flags, source_of = ["possible_emergency"], {"possible_emergency": "model"}
        source = "model+safety_net" if rule_flags and model_em else "safety_net" if rule_flags else "model"
        rule = "+".join(r for r, on in (("red_flag", bool(rule_flags)), ("model_emergency", model_em)) if on)
        return Route(Decision("emergency", "immediate", 1.0, rule), source, emergency=flags, flag_source=source_of)

    # 2) the care type: the model's top non-emergency class
    d_rules = decide(ex)
    probs = {k: v for k, v in so.care.items() if k != "emergency"}
    care = max(probs, key=probs.get)
    source, rule, llm_urgency = "model", f"model_{care}", None
    ask_unsure = False
    opinion = None
    if so.band == "low":
        fired.add("low_confidence")
        opinion = llm_fallback.ask(user_text, history)  # None when switched off or on any error
        if opinion is not None:
            fired.add("llm_fallback")
            if opinion.says_emergency:  # Claude may add an emergency, never remove one
                flags = [RED_FLAG_INTERNAL.get(f, f) for f in opinion.red_flags] or ["possible_emergency"]
                return Route(Decision("emergency", "immediate", 1.0, "llm_emergency"), "llm", emergency=flags,
                             flag_source={f: "llm" for f in flags}, llm=opinion)
            care, source, rule, llm_urgency = opinion.care or FOLLOWUP, "llm", "llm", opinion.urgency
        elif policy == "conversational" and interactive:
            ask_unsure = True
        elif d_rules.care:
            care, source, rule = d_rules.care, "safety_net", d_rules.rule + "+model_unsure"
    if care == FOLLOWUP and so.band != "high" and d_rules.care and source == "model":
        # the model would ask, without much confidence, but the words already name a service or a
        # symptom the rules can route: decide instead of asking (fewer questions, same safety)
        care, source, rule = d_rules.care, "safety_net", d_rules.rule + "+model_unsure"
        fired.add("low_confidence")
    if care == OUT_OF_SCOPE:
        fired.add("out_of_scope")

    # 3) ask, or decide
    needs = [n for n in d_rules.needs if n == "age"]  # a child's fever with no age: a baby could be an emergency
    if care == FOLLOWUP:
        needs.append("main_symptom")
    elif care == OUT_OF_SCOPE:
        needs.append("scope")
    decided = care if care in CARE_KEYS else None
    service = _is_service(ex, decided)
    p_care = so.care.get("gp" if care == "specialist" else care, 0.0)
    qid = None
    if interactive:
        if (so.care.get("emergency", 0.0) >= 0.5 and "q_danger" not in asked
                and len(asked) < config.MAX_FOLLOWUPS):
            # the model senses danger but no red flag is named: ask about danger signs first
            # (a "Haan" goes to the emergency path) rather than calling 112 on the model alone
            qid = "q_danger"
            fired.add("model_emergency")
        else:
            qid = followup.choose(ex, Decision(decided, None, p_care, rule, needs=needs), asked, policy,
                                  service=service, who=so.top_who)
        if (qid is None and ask_unsure and "q_main_symptom" not in asked
                and len(asked) < config.MAX_FOLLOWUPS):
            qid = "q_main_symptom"  # unsure and nothing else to ask: what is needed?
    if qid:
        return Route(Decision(None, None, round(p_care, 2), rule, needs=needs), source, qid=qid, llm=opinion)

    if (decided is None or ask_unsure) and d_rules.care:  # no question left: the rules' choice, if any
        decided, source, rule = d_rules.care, "safety_net", d_rules.rule + "+model_unsure"
    if decided is None:
        return Route(Decision(None, None, round(p_care, 2), rule), source, llm=opinion)

    # fever is checked in person (the organisers label fever + cough as a medic visit), unless
    # the person asked for a doctor on the phone
    if decided == "gp" and "fever" in ex.symptom_ids() and not any(h.id == "teleconsult" for h in ex.services):
        decided, rule = "paramedic", rule + "+fever_home_visit"
        fired.add("fever_home_visit")
        if source == "model":
            source = "model+safety_net"

    # 4) urgency: the model's (never "immediate" here), then the floors
    if source == "llm" and llm_urgency in ("routine", "same_day"):
        urgency = llm_urgency
    elif decided == "lab":
        urgency = "routine"  # home sample collection is scheduled unless something raises it
    else:
        urgency = "same_day" if so.top_urgency == "immediate" else so.top_urgency
    rules_urgency = "same_day" if d_rules.urgency == "immediate" else d_rules.urgency
    if rules_urgency in URGENCY_ORDER and urgency_rank(rules_urgency) > urgency_rank(urgency):
        urgency = rules_urgency
        fired.add("urgency_floor")
        rule += "+urgency_floor"
    # an older adult's requested service is booked for its own sake (as in the rules)
    if who in VULNERABLE and not (service and who == "elderly") and urgency_rank(urgency) < urgency_rank("same_day"):
        urgency = "same_day"
        fired.add("vulnerable_floor")
        rule += "+vulnerable_floor"
    if source == "model" and fired & {"urgency_floor", "vulnerable_floor"}:
        source = "model+safety_net"
    p = so.care.get("gp" if decided == "specialist" else decided, 0.0)
    return Route(Decision(decided, urgency, round(p, 2), rule,
                          specialty=d_rules.specialty if decided == d_rules.care else None), source, llm=opinion)


# ---- what we understood (trace.structured) -----------------------------------

def _who(ex: Extraction, so: StudentOutput | None) -> str:
    """Who the patient is: from the words (age, pregnancy, relation) first, else the model."""
    if ex.pregnant:
        return "pregnant"
    group = {"infant": "infant", "child": "child", "older_adult": "elderly"}.get(ex.age_group or "")
    if group:
        return group
    if ex.age_group == "adult":
        return "self" if ex.relation == "self" else "adult"
    if so is not None:
        return so.top_who
    if ex.relation == "self":
        return "self"
    if ex.relation in ("father", "mother", "wife", "husband"):
        return "adult"
    return "child" if ex.relation == "child" else "unknown"


def _intake_items(ex: Extraction, so: StudentOutput | None) -> list[tuple[str, dict[str, str]]]:
    """Symptoms and services with their labels in each language: the model's tags first (by
    the lexicon's label where the id is the same), then anything else the lexicon found."""
    from .nlp.lexicon import get_lexicon

    by_id = get_lexicon().by_id
    items: list[tuple[str, dict[str, str]]] = []
    seen: set[str] = set()

    def add(item_id: str, labels: dict[str, str]) -> None:
        if item_id not in seen:
            seen.add(item_id)
            items.append((item_id, labels))

    for tag in (so.tags_on() if so is not None else []):
        e = by_id.get(tag)
        if e is not None and e.kind in ("symptom", "service", "red_flag"):
            add(tag, {"en": e.label, "hinglish": e.label_hinglish, "hi": e.label_hi})
        else:
            add(tag, {lang: text.tag_label(tag, lang) for lang in text.LANGS})
    for h in ex.symptoms + ex.services:
        add(h.id, {"en": h.entry.label, "hinglish": h.entry.label_hinglish, "hi": h.entry.label_hi})
    return items


def _structured(items: list[tuple[str, dict[str, str]]], ex: Extraction, who: str, language: str) -> dict:
    lang = text.lang_of(language)
    return {
        "symptoms": [{"id": i, "label": labels["en"], "label_local": labels[lang]} for i, labels in items],
        "who": who, "who_label": text.WHO_LABELS[who]["en"], "who_label_local": text.WHO_LABELS[who][lang],
        "duration_days": ex.duration_days,
        "age_years": None if ex.age_years is None else round(ex.age_years, 2),
    }


def _student_trace(student: Any, so: StudentOutput) -> dict:
    meta = getattr(student, "meta", {}) or {}
    return {
        "name": getattr(student, "name", "MuRIL (fine-tuned)"),
        "probabilities": {k: round(v, 3) for k, v in sorted(so.care.items())},
        "urgency_probabilities": {k: round(v, 3) for k, v in sorted(so.urgency.items())},
        "confidence": so.confidence, "band": so.band,
        "flags": so.flags_on(),
        "version": meta.get("version") or meta.get("trained_at"),
        "latency_ms": so.latency_ms,
    }


# the age itself in an answer to the age question ("3 saal", "8 mahine ka", "५ साल")
AGE_SPAN = re.compile(r"(\d+(\.\d+)?|ek|do|teen|char|paanch|chhe|saat|aath|nau|das|dedh|dhai|one|two|three|four|five"
                      r"|six|seven|eight|nine|ten)\s*(saal|sal|years?|yrs?|mahine|mahina|months?|hafte|weeks?|din|days?)"
                      r"(\s+(ka|ki|ke|old))?", re.I)
FILLER_ANSWER = {"hai", "hain", "he", "h", "ji", "haan", "ha", "the", "is", "of", "and", "aur", "ka", "ki", "ke",
                 "se", "kam", "zyada", "jyada", "ya", "or", "less", "more", "than", "under", "over", "above",
                 "older", "about", "around", "lagbhag", "approx", "umar", "age"}


def _answer_text(qid: str, answer: str, before: list[str], language: str | None) -> str | None:
    """What of an answer to one of our fact questions also counts as free text.
    The fact itself is read by parse_answer: a duration answer may join as it is (it says
    the same duration); an age answer joins without its age ("3 saal, ulti bhi" adds
    vomiting, not a 3-year illness); a yes/no answer joins only if it adds something."""
    text = (answer or "").strip()
    if not text:
        return None
    if qid == "q_duration":
        return text
    if qid == "q_who" and followup.option_value(qid, text):  # a tapped option is only the fact
        return None
    if qid in ("q_age", "q_who"):  # "mere papa, 72 saal" joins as "mere papa"
        rest = AGE_SPAN.sub(" ", to_roman(text))
        words = [w for w in re.findall(r"[a-z]+", rest.lower()) if w not in FILLER_ANSWER]
        return rest if words else None

    def found(texts: list[str]) -> set[str]:
        if not texts:
            return set()
        ex = extract(" . ".join(texts), language)
        return {h.id for h in ex.red_flags + ex.symptoms + ex.services}
    return text if found(before + [text]) - found(before) else None


def run(req: TriageRequest, mode: str = "interactive", policy: str | None = None,
        explain: bool = False, use_model: bool = True) -> TriageResponse:
    t0 = time.perf_counter()
    turns = read_history(req.conversation_history) + [Turn("user", req.user_input or "")]

    # pair each of our questions with the user turn that answers it
    asked: list[str] = []
    answers: dict[str, str] = {}
    free_text: list[str] = []
    pending: str | None = None
    for turn in turns:
        if turn.role == "assistant":
            pending = turn.question_id
            if pending:
                asked.append(pending)
            continue
        if pending and pending not in answers:
            answers[pending] = turn.text
            if pending in STRUCTURED_ANSWERS:
                extra = _answer_text(pending, turn.text, free_text, req.language)
                pending = None
                if extra:  # "2 din se, aur ab behosh ho gaye" still carries an emergency
                    free_text.append(extra)
                continue
        pending = None
        if turn.text.strip():
            free_text.append(turn.text)

    facts: dict = {}
    for qid, ans in answers.items():
        facts.update(followup.parse_answer(qid, ans))

    combined = " . ".join(free_text)
    ex = extract(combined, req.language, age_years=facts.get("age_years"),
                 duration_days=facts.get("duration_days"))
    if facts.get("pregnant") and not ex.pregnant:  # "Garbhvati mahila" picked in answer to q_who
        ex.pregnant = True
    language = ex.language if (req.language or "auto") == "auto" else text.lang_of(ex.language)
    out_lang = language if config.REASONING_LANGUAGE == "user" else "en"

    flag_ids = [h.id for h in ex.red_flags]
    breathing = "present" if "breathing_difficulty" in flag_ids else (
        "absent" if "breathing_difficulty" in ex.negated_flags else "not_reported")
    if facts.get("breathing") == "present" and "breathing_difficulty" not in flag_ids:
        flag_ids.append("breathing_difficulty")
        breathing = "present"
    elif facts.get("breathing") == "absent" and breathing != "present":
        breathing = "absent"
    # "Haan" to the danger-signs question is an emergency; "Nahi" also answers the breathing check
    if facts.get("danger") == "present" and "possible_emergency" not in flag_ids:
        flag_ids.append("possible_emergency")
    elif facts.get("danger") == "absent" and breathing == "not_reported":
        breathing = "absent"

    lex = ex_entries(ex)
    trace: dict[str, Any] = {"version": VERSION, "language": language, "mode": mode,
                             "understood": _understood(ex, language)}
    sl = text.speech_lang(language)  # read-aloud text is Hindi or English (trace.speech)
    interactive = mode == "interactive"

    # the fine-tuned model reads the whole conversation, when it is loaded
    student = get_student() if use_model else None
    so: StudentOutput | None = None
    history = [(t.role, t.text) for t in turns[:-1]]
    if student is not None:
        try:
            # Devanagari typed without spaces is cut into words first, as the lexicon does
            lexicon = get_lexicon()
            so = student.predict(lexicon.space_devanagari(req.user_input or ""),
                                 [(role, lexicon.space_devanagari(t)) for role, t in history])
        except Exception:  # never take the API down because of the model
            log.exception("student prediction failed; using rules + the old model")
    if so is not None:
        trace["model"] = _student_trace(student, so)
    who = _who(ex, so)
    items = _intake_items(ex, so)
    trace["structured"] = _structured(items, ex, who, language)
    trace["safety_net_local"] = None
    fired: set[str] = set()  # guardrails that changed or decided something (trace.guardrails)

    def emergency(flags: list[str], rule: str, source: str, flag_source: dict[str, str] | None = None) -> TriageResponse:
        """Emergency path: skips matching, always shows call-for-help."""
        flags = _merge_flags(flags)
        labels_en = [lex[f].label for f in flags]
        labels_local = [lex[f].label_for(language) for f in flags]
        why_en, why_local = text.emergency_reasoning(labels_en, labels_local, language)
        d_em = Decision("emergency", "immediate", 1.0, rule)
        resp = dict(follow_up_question=None, care_type=api_care("emergency"), urgency=api_urgency("immediate"),
                    red_flags=config.api_flags(flags), reasoning=why_local if out_lang != "en" else why_en,
                    matched_caregivers=[])
        # what in the words (or which answer) raised each flag; nothing to quote for the model's own
        evidence = {"breathing_difficulty": answers.get("q_breathing", ""),
                    "possible_emergency": answers.get("q_danger", "")} | {h.id: h.evidence for h in ex.red_flags}
        trace.update({
            "checks": _checks(ex, breathing, flags, language),
            "red_flags": [{"id": f, "label": lex[f].label, "label_local": lex[f].label_for(language),
                           "evidence": evidence.get(f, ""),
                           "source": (flag_source or {}).get(f, "rules")} for f in flags],
            "decision": _decision_trace("emergency", "immediate", d_em, language, source),
            "reasoning_local": why_local, "follow_up": None,
            "emergency": text.emergency_block(flags, language), "caregivers": [],
            "speech": text.speech([text.EMERGENCY_TITLE[sl], *text.EMERGENCY_STEPS[sl][:2]], language),
            "guardrails": text.guardrails(fired, language),
        })
        return _finish(resp, trace, t0, explain)

    if so is not None:
        # model first; the rules' red flags are the safety net
        route = _model_first(so, ex, flag_ids, asked, policy, interactive, req.user_input or "", history, who, fired)
        if route.llm is not None:
            o = route.llm
            trace["llm"] = {"model": o.model, "care_type": api_care(o.care), "urgency": api_urgency(o.urgency),
                            "red_flags": o.red_flags, "reasoning": text.scrub(o.reasoning), "latency_ms": o.latency_ms}
        if route.emergency:
            return emergency(route.emergency, route.decision.rule, route.source, route.flag_source)
        d, source, qid = route.decision, route.source, route.qid
    else:
        # 1) red flag: emergency path
        if flag_ids:
            fired.add("safety_net")
            return emergency(flag_ids, "red_flag", "rules")

        # 2) decide (rules, then the learned model on every request), or ask one question
        d = decide(ex)
        source, model_probs = "rules", {}
        if use_model:
            d, model_emergency, source, model_probs = _apply_model(ex, d, combined)
            if model_emergency:
                fired.add("model_emergency")
                return emergency(["possible_emergency"], "model_emergency", "model")
        if source == "rules" and d.care:
            d = Decision(d.care, care_urgency(d.care, d.urgency), d.confidence, d.rule, needs=d.needs,
                         specialty=d.specialty)
        if model_probs:
            trace["model"] = {"name": "TF-IDF + logistic regression",
                              "probabilities": {k: round(v, 3) for k, v in sorted(model_probs.items())},
                              "version": get_model().meta.get("trained_at") if get_model() else None}
        qid = followup.choose(ex, d, asked, policy, service=_is_service(ex, d.care)) if interactive else None
    if qid:
        q = followup.question(qid, language)
        resp = dict(follow_up_question=q.text, care_type=None, urgency=None, red_flags=[],
                    reasoning=ASK_REASON[qid]["en" if out_lang == "en" else text.lang_of(language)],
                    matched_caregivers=[])
        trace.update({
            "checks": _checks(ex, breathing, [], language), "red_flags": [],
            "decision": _decision_trace(None, None, d, language, source if so is not None else "rules")
            | {"rule": d.rule},
            "reasoning_local": ASK_REASON[qid][text.lang_of(language)],
            "follow_up": {"id": q.id, "text": q.text, "kind": q.kind, "options": q.options,
                          "asked_so_far": len(asked) + 1, "max": config.MAX_FOLLOWUPS},
            "emergency": None, "caregivers": [],
            "speech": text.speech([followup.question(qid, sl).text], language),
            "guardrails": text.guardrails(fired, language),
        })
        return _finish(resp, trace, t0, explain)

    care, urgency = d.care, d.urgency
    if care is None:  # nothing understood and no more questions: safe default
        care, urgency = "gp", "same_day"
        d = Decision(care, urgency, 0.2, "fallback_unclear")

    # 3) match caregivers
    loc = (req.location.lat, req.location.lng) if req.location else None
    matches = rank(care, urgency, ex, loc, specialty=d.specialty)
    lang = text.lang_of(language)
    named = bool(ex.symptoms or ex.services)
    # the model decided from words the lexicon does not know: say it with the model's tags
    labels = None if named or so is None else {lg: [lb[lg] for _, lb in items] for lg in text.LANGS}
    understood_any = named or (so is not None and d.rule != "fallback_unclear")

    def why(lg: str) -> str:
        return text.reasoning(ex, care, urgency, breathing, lg, labels=labels[lg] if labels else None)

    why_en = why("en") if understood_any else \
        "The problem was not clear; a doctor teleconsult today is the safe default."
    unclear = {"en": why_en, "hinglish": "Taklif saaf nahi hui; aaj doctor se phone par baat karna sabse surakshit hai.",
               "hi": "तकलीफ़ साफ़ नहीं हुई; आज डॉक्टर से फ़ोन पर बात करना सबसे सुरक्षित है।"}
    why_local = why(language) if understood_any else unclear[lang]
    why_said = why(sl) if understood_any else unclear[sl]
    if text.has_banned(why_en) or text.has_banned(why_local):
        fired.add("clinical_scope")
    resp = dict(
        follow_up_question=None, care_type=api_care(care), urgency=api_urgency(urgency), red_flags=[],
        reasoning=text.scrub(why_local if out_lang != "en" else why_en),
        matched_caregivers=[MatchedCaregiver(caregiver_id=m.caregiver.id, score=m.score,
                                             reason=m.reason_local if out_lang != "en" else m.reason)
                            for m in matches],
    )
    item_ids = {i for i, _ in items}
    trace.update({
        "checks": _checks(ex, breathing, [], language), "red_flags": [],
        "decision": _decision_trace(care, urgency, d, language, source),
        "reasoning_local": text.scrub(why_local), "follow_up": None, "emergency": None,
        "speech": text.speech([why_said], language),
        "safety_net_local": text.safety_net(language, fever="fever" in item_ids, child=who in ("child", "infant")),
        "guardrails": text.guardrails(fired, language),
        "caregivers": [{
            "caregiver_id": m.caregiver.id, "name": m.caregiver.name, "role": m.caregiver.role,
            "languages": m.caregiver.languages, "skills": m.caregiver.skills,
            "distance_km": m.distance_km,
            "next_slot": m.next_slot.isoformat() if m.next_slot else None,
            "next_slot_label": m.slot_label, "next_slot_label_local": m.slot_label_local,
            "rating": m.caregiver.rating, "score": m.score, "reason": m.reason, "reason_local": m.reason_local,
            "features": m.features,
        } for m in matches],
    })
    return _finish(resp, trace, t0, explain)


def _enforce(resp: dict) -> bool:
    """Last check of the response contract; True if something had to be corrected. An
    emergency has red flags, no question and no caregivers; a question has no decision;
    nothing else carries the emergency urgency."""
    em_care, em_urgency = api_care("emergency"), api_urgency("immediate")
    before = (resp["follow_up_question"], resp["care_type"], resp["urgency"], list(resp["red_flags"]),
              len(resp["matched_caregivers"]))
    if resp["red_flags"] or resp["care_type"] == em_care:
        resp.update(follow_up_question=None, care_type=em_care, urgency=em_urgency, matched_caregivers=[],
                    red_flags=resp["red_flags"] or ["possible_emergency"])
    elif resp["follow_up_question"]:
        resp.update(care_type=None, urgency=None, matched_caregivers=[])
    elif resp["urgency"] == em_urgency:
        resp["urgency"] = api_urgency("same_day")
    return before != (resp["follow_up_question"], resp["care_type"], resp["urgency"], list(resp["red_flags"]),
                      len(resp["matched_caregivers"]))


def _finish(resp: dict, trace: dict, t0: float, explain: bool) -> TriageResponse:
    if _enforce(resp):
        log.warning("response corrected by the final invariants check")
        lang = text.lang_of(trace.get("language", "en"))
        for g in trace.get("guardrails") or []:
            if g["id"] == "invariants":
                note = text.GUARDRAILS["invariants"]["fired"]
                g.update(status="fired", note=note["en"], note_local=note[lang])
    trace["timing_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    if explain:
        return TriageResponseWithTrace(**resp, trace=trace)
    return TriageResponse(**resp)

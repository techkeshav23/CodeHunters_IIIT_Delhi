"""One request in, one decision out: read the conversation, check red flags,
extract facts, decide (or ask), match caregivers, explain."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from . import config
from .config import VERSION, api_care, api_urgency
from .matching.ranker import rank
from .nlp.extract import Extraction, extract
from .schemas import MatchedCaregiver, TriageRequest, TriageResponse, TriageResponseWithTrace
from .triage import followup, text
from .triage.rules import Decision, decide

USER_ROLES = {"user", "patient", "human", "customer", "client"}
ASSISTANT_ROLES = {"assistant", "bot", "system", "agent", "ai", "app"}
STRUCTURED_ANSWERS = {"q_age", "q_duration", "q_breathing"}  # read via parse_answer, not as free text

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
            qid = followup.identify(item)
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


def _decision_trace(care: str | None, urgency: str | None, d: Decision, language: str) -> dict:
    lang = text.lang_of(language)
    return {
        "care_type": api_care(care), "urgency": api_urgency(urgency),
        "care_label": text.CARE_LABELS[care]["en"] if care else None,
        "care_label_local": text.CARE_LABELS[care][lang] if care else None,
        "urgency_label": text.URGENCY_LABELS[urgency]["en"] if urgency else None,
        "urgency_label_local": text.URGENCY_LABELS[urgency][lang] if urgency else None,
        "confidence": round(d.confidence, 2), "source": "rules", "rule": d.rule,
        "specialty": d.specialty,
    }


def run(req: TriageRequest, mode: str = "interactive", policy: str | None = None,
        explain: bool = False) -> TriageResponse:
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
                pending = None
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

    lex = ex_entries(ex)
    trace: dict[str, Any] = {"version": VERSION, "language": language, "mode": mode,
                             "understood": _understood(ex, language)}

    # 1) emergency path: skips matching
    if flag_ids:
        labels_en = [lex[f].label for f in flag_ids]
        labels_local = [lex[f].label_for(language) for f in flag_ids]
        why_en, why_local = text.emergency_reasoning(labels_en, labels_local, language)
        d = Decision("emergency", "immediate", 1.0, "red_flag")
        resp = dict(follow_up_question=None, care_type=api_care("emergency"), urgency=api_urgency("immediate"),
                    red_flags=flag_ids, reasoning=why_local if out_lang != "en" else why_en, matched_caregivers=[])
        evidence = {h.id: h.evidence for h in ex.red_flags}
        trace.update({
            "checks": _checks(ex, breathing, flag_ids, language),
            "red_flags": [{"id": f, "label": lex[f].label, "label_local": lex[f].label_for(language),
                           "evidence": evidence.get(f, answers.get("q_breathing", ""))} for f in flag_ids],
            "decision": _decision_trace("emergency", "immediate", d, language),
            "reasoning_local": why_local, "follow_up": None,
            "emergency": text.emergency_block(flag_ids, language), "caregivers": [],
        })
        return _finish(resp, trace, t0, explain)

    # 2) decide, or ask one question
    d = decide(ex)
    qid = followup.choose(ex, d, asked, policy) if mode == "interactive" else None
    if qid:
        q = followup.question(qid, language)
        resp = dict(follow_up_question=q.text, care_type=None, urgency=None, red_flags=[],
                    reasoning=ASK_REASON[qid]["en" if out_lang == "en" else text.lang_of(language)],
                    matched_caregivers=[])
        trace.update({
            "checks": _checks(ex, breathing, [], language), "red_flags": [],
            "decision": _decision_trace(None, None, d, language) | {"rule": d.rule},
            "reasoning_local": ASK_REASON[qid][text.lang_of(language)],
            "follow_up": {"id": q.id, "text": q.text, "kind": q.kind, "options": q.options,
                          "asked_so_far": len(asked) + 1, "max": config.MAX_FOLLOWUPS},
            "emergency": None, "caregivers": [],
        })
        return _finish(resp, trace, t0, explain)

    care, urgency = d.care, d.urgency
    if care is None:  # nothing understood and no more questions: safe default
        care, urgency = "gp", "same_day"
        d = Decision(care, urgency, 0.2, "fallback_unclear")

    # 3) match caregivers
    loc = (req.location.lat, req.location.lng) if req.location else None
    matches = rank(care, urgency, ex, loc, specialty=d.specialty)
    why_en = text.reasoning(ex, care, urgency, breathing, "en") if ex.symptoms or ex.services else \
        "The problem was not clear; a doctor teleconsult today is the safe default."
    why_local = text.reasoning(ex, care, urgency, breathing, language) if ex.symptoms or ex.services else \
        {"en": why_en, "hinglish": "Taklif saaf nahi hui; aaj doctor se phone par baat karna sabse surakshit hai.",
         "hi": "तकलीफ़ साफ़ नहीं हुई; आज डॉक्टर से फ़ोन पर बात करना सबसे सुरक्षित है।"}[text.lang_of(language)]
    resp = dict(
        follow_up_question=None, care_type=api_care(care), urgency=api_urgency(urgency), red_flags=[],
        reasoning=text.scrub(why_local if out_lang != "en" else why_en),
        matched_caregivers=[MatchedCaregiver(caregiver_id=m.caregiver.id, score=m.score,
                                             reason=m.reason_local if out_lang != "en" else m.reason)
                            for m in matches],
    )
    trace.update({
        "checks": _checks(ex, breathing, [], language), "red_flags": [],
        "decision": _decision_trace(care, urgency, d, language),
        "reasoning_local": text.scrub(why_local), "follow_up": None, "emergency": None,
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


def _finish(resp: dict, trace: dict, t0: float, explain: bool) -> TriageResponse:
    trace["timing_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    if explain:
        return TriageResponseWithTrace(**resp, trace=trace)
    return TriageResponse(**resp)

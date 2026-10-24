"""Rule-based triage: the safety net and the fallback when no model is loaded.

Placeholder routing until the doctor-labelled train set arrives: each symptom
in lexicon.yaml carries an `acute` and a `chronic` [care, urgency] pair, and
the most urgent one wins. Red flags always mean emergency / immediate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import URGENCY_ORDER, urgency_rank
from ..nlp.extract import Extraction

CHRONIC_DAYS = 14
CARE_PRIORITY = ["emergency", "paramedic", "nurse", "specialist", "gp"]  # tie-break, most hands-on first


@dataclass
class Decision:
    care: str | None
    urgency: str | None
    confidence: float
    rule: str
    needs: list[str] = field(default_factory=list)  # info that could change the decision
    specialty: str | None = None


def _bump(urgency: str, to: str) -> str:
    return to if urgency_rank(to) > urgency_rank(urgency) else urgency


def decide(ex: Extraction) -> Decision:
    if ex.red_flags:
        return Decision("emergency", "immediate", 1.0, "red_flag")

    needs: list[str] = []
    symptoms = [h.entry for h in ex.symptoms]
    services = [h.entry for h in ex.services]

    if ex.pregnant and not symptoms:
        return Decision("specialist", "routine", 0.6, "pregnancy_routine", specialty="gynaecology")
    if not symptoms and not services:
        return Decision(None, None, 0.0, "no_symptom_understood", needs=["main_symptom"])

    chronic = ex.duration_days is not None and ex.duration_days >= CHRONIC_DAYS
    if ex.duration_days is None and any(s.meta.get("needs_duration") for s in symptoms):
        needs.append("duration")

    vulnerable = ex.age_group in ("infant", "child", "older_adult") or bool(ex.pregnant)
    mild = "mild" in ex.severity and "severe" not in ex.severity and not vulnerable
    best: tuple[str, str, str | None, str] | None = None  # care, urgency, specialty, rule
    for s in symptoms:
        care, urg = s.meta.get("chronic" if chronic else "acute") or ["gp", "routine"]
        if mild and not chronic and s.id == "fever":  # "halka bukhar" in an adult: teleconsult
            care, urg = "gp", "routine"
        cand = (care, urg, s.meta.get("specialty"), f"{'chronic' if chronic else 'acute'}_{s.id}")
        if best is None or (urgency_rank(cand[1]), -CARE_PRIORITY.index(cand[0])) > \
                (urgency_rank(best[1]), -CARE_PRIORITY.index(best[0])):
            best = cand

    # a direct request ("injection lagwana hai", "BP check karwana hai") decides the care type;
    # physiotherapy is more specific than general post-operative nursing
    only_conditions = bool(symptoms) and all(s.meta.get("condition") for s in symptoms)
    physio = next((sv for sv in services if sv.id == "physiotherapy"), None)
    nurse_service = next((sv for sv in services if sv.meta.get("care") == "nurse"), None)
    if services and (best is None or nurse_service or physio or only_conditions):
        sv = physio or nurse_service or services[0]
        care = sv.meta.get("care", "gp")
        urg = "routine" if (best is None or only_conditions) else best[1]
        best = (care, urg, "physiotherapy" if sv is physio else None, f"service_{sv.id}")

    care, urgency, specialty, rule = best
    confidence = 0.7 if len(symptoms) + len(services) >= 1 else 0.3

    # age and severity raise urgency for new problems
    # (not for a child over 2 whose problem is called mild: "halki sardi", playing and feeding well)
    mild_child = (ex.age_group == "child" and (ex.age_years is None or ex.age_years >= 2)
                  and "mild" in ex.severity and "severe" not in ex.severity)
    if not chronic and symptoms and ex.age_group in ("infant", "child", "older_adult") and not mild_child:
        urgency = _bump(urgency, "same_day")
        rule += f"+{ex.age_group}"
    if not chronic and "severe" in ex.severity:
        urgency = _bump(urgency, "same_day")
        rule += "+severe"

    # chest pain or breathlessness that came and settled still needs someone to look today
    if ex.settled_flags:
        urgency = _bump(urgency, "same_day")
        if care in ("gp", "specialist", "nurse"):
            care = "paramedic"
        rule += "+settled_" + "_".join(sorted(ex.settled_flags))
    # a child with fever whose age we do not know: a young baby would be an emergency
    if "fever" in ex.symptom_ids() and ex.age_years is None and ex.relation == "child":
        needs.append("age")
        confidence = min(confidence, 0.5)
    if needs:
        confidence = min(confidence, 0.55)
    if any(h.entry.meta.get("generic") for h in ex.symptoms):
        confidence = min(confidence, 0.45)
    assert urgency in URGENCY_ORDER
    return Decision(care, urgency, confidence, rule, needs=needs, specialty=specialty)

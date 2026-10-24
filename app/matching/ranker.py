"""Caregiver ranking: a role filter, then a weighted score, with reasons built
only from computed facts (distance, free time, language, skills). Far, busy or
other-specialty caregivers are demoted, not removed, so the list is never empty
while someone of the right role exists."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .. import config
from ..nlp.extract import Extraction
from .caregivers import Caregiver, load, next_free, now

WEIGHTS = {
    "home": {"skill": 0.25, "time": 0.25, "distance": 0.25, "language": 0.15, "rating": 0.10},
    "tele": {"skill": 0.25, "time": 0.35, "distance": 0.00, "language": 0.25, "rating": 0.15},
    "specialist": {"skill": 0.35, "time": 0.20, "distance": 0.10, "language": 0.20, "rating": 0.15},
}
LANGUAGE_WORDS = {"hindi", "english", "punjabi", "urdu", "bengali", "bangla", "tamil", "telugu", "malayalam",
                  "marathi", "gujarati", "kannada", "bhojpuri", "odia", "konkani"}
FEMALE_WORDS = {"lady", "ladies", "female", "mahila", "woman", "aurat"}
LANG_HI = {"Hindi": "हिंदी", "English": "अंग्रेज़ी", "Punjabi": "पंजाबी", "Urdu": "उर्दू", "Tamil": "तमिल",
           "Malayalam": "मलयालम", "Bengali": "बंगाली", "Telugu": "तेलुगु", "Marathi": "मराठी",
           "Bhojpuri": "भोजपुरी", "Konkani": "कोंकणी", "Gujarati": "गुजराती", "Kannada": "कन्नड़"}
# words that name each specialty in a caregiver's role, specialty or skills;
# "*" marks a stem ("cardi*" matches cardiology and cardiac), the rest are whole words
SPECIALTY_ALIASES = {
    "paediatrics": ("paediatr*", "pediatr*", "paeds", "peds", "child*"),
    "gynaecology": ("gynae*", "gyne*", "gynec*", "obstet*", "obg", "obs", "pregnan*", "women's health", "maternity"),
    "orthopaedics": ("orthopaed*", "orthoped*", "ortho", "bone*", "joint*"),
    "physiotherapy": ("physio*",),
    "cardiology": ("cardi*", "heart"),
    "dermatology": ("derma*", "skin"),
    "psychiatry": ("psych*", "mental health"),
    "neurology": ("neuro*",),
    "gastroenterology": ("gastro*", "digestive", "stomach", "hepat*"),
    "urology": ("uro*", "kidney*"),
    "ophthalmology": ("ophthalm*", "eye*"),
    "ent": ("ent", "ear nose", "otolaryng*", "otorhino*"),
    "dental": ("dent*", "tooth", "teeth", "oral"),
}
SPECIALIST_ROLE = re.compile(r"(ologist|iatrist|iatrician|dentist|surgeon|therapist)\b")
NOT_SPECIALIST = re.compile(r"technolog|technician|attendant|assistant|\banm\b|\basha\b|aide")


@dataclass
class Match:
    caregiver: Caregiver
    score: float
    distance_km: float | None
    next_slot: datetime | None
    reason: str
    reason_local: str
    slot_label: str | None
    slot_label_local: str | None
    features: dict


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _role_ok(cg: Caregiver, care: str) -> bool:
    roles = config.ROLES_FOR_CARE.get(care, [])
    if any(r == cg.role or r in cg.role for r in roles):
        return True
    if care != "specialist":
        return False
    # "Cardiologist", "Dentist", or a doctor with a named specialty (not a nurse or paramedic)
    home_roles = config.ROLES_FOR_CARE["nurse"] + config.ROLES_FOR_CARE["paramedic"]
    if NOT_SPECIALIST.search(cg.role):  # "ECG technologist", "ANM"
        return False
    return bool(SPECIALIST_ROLE.search(cg.role)) or (
        bool(cg.specialty) and cg.specialty not in ("general", "general medicine", "none")
        and not any(r in cg.role for r in home_roles))


def _specialty_ok(cg: Caregiver, specialty: str | None) -> bool:
    if not specialty:
        return True
    if "physio" in cg.role:  # a physiotherapist's "cardiac rehab" skill does not make a cardiologist
        return specialty == "physiotherapy"
    # the declared specialty decides; skills only when there is none ("family planning counselling"
    # in a gynaecologist's skills is not psychiatry)
    hay = " ".join([cg.role, cg.specialty] if cg.specialty else [cg.role] + cg.skills)
    for name in SPECIALTY_ALIASES.get(specialty, (specialty + "*",)):
        stem = name.endswith("*")
        if re.search(r"\b" + re.escape(name.rstrip("*")) + ("" if stem else r"\b"), hay):
            return True
    return False


def preferred_languages(ex: Extraction) -> list[str]:
    asked = [t.title() for t in ex.tokens if t in LANGUAGE_WORDS]
    base = ["English"] if ex.language == "en" else ["Hindi"]
    return list(dict.fromkeys(asked + base))


def needed_skills(ex: Extraction, care: str, specialty: str | None) -> list[str]:
    skills = [h.entry.meta["skill"] for h in ex.services if h.entry.meta.get("skill")]
    if ex.age_group in ("infant", "child"):
        skills.append("pediatric")
    if ex.age_group == "older_adult" and care in ("paramedic", "nurse", "gp"):
        skills.append("elderly care")
    if "fever" in ex.symptom_ids() and care == "paramedic":
        skills.append("fever care")
    return list(dict.fromkeys(skills))


def _slot_labels(dt: datetime | None, ref: datetime) -> tuple[str | None, str | None, str | None]:
    """English, Hinglish and Hindi labels: "4 pm" / "tomorrow 10 am" / "Sat 10 am"."""
    if dt is None:
        return None, None, None
    h12 = dt.hour % 12 or 12
    clock = f"{h12}" if dt.minute == 0 else f"{h12}:{dt.minute:02d}"
    ampm = "am" if dt.hour < 12 else "pm"
    part_hl = "subah" if dt.hour < 12 else "dopahar" if dt.hour < 16 else "shaam" if dt.hour < 19 else "raat"
    part_hi = {"subah": "सुबह", "dopahar": "दोपहर", "shaam": "शाम", "raat": "रात"}[part_hl]
    days = (dt.date() - ref.date()).days
    if days <= 0:
        return f"{clock} {ampm}", f"aaj {part_hl} {clock} baje", f"आज {part_hi} {clock} बजे"
    if days == 1:
        return f"tomorrow {clock} {ampm}", f"kal {part_hl} {clock} baje", f"कल {part_hi} {clock} बजे"
    wd = dt.strftime("%a")
    return f"{wd} {clock} {ampm}", f"{wd} {part_hl} {clock} baje", f"{wd} {part_hi} {clock} बजे"


def rank(care: str, urgency: str, ex: Extraction, location: tuple[float, float] | None,
         specialty: str | None = None, top_k: int | None = None,
         caregivers: list[Caregiver] | None = None, ref: datetime | None = None) -> list[Match]:
    if care == "emergency":
        return []
    top_k = top_k or config.TOP_K
    pool = caregivers if caregivers is not None else load()[0]
    ref = ref or now()
    mode = "tele" if care in config.TELE_CARE else "specialist" if care == "specialist" else "home"
    w = WEIGHTS[mode]
    window_h = config.SAME_DAY_WINDOW_H if urgency == "same_day" else config.ROUTINE_WINDOW_H
    want_langs = preferred_languages(ex)
    want_skills = needed_skills(ex, care, specialty)
    want_female = any(t in FEMALE_WORDS for t in ex.tokens)

    # specialists of the right specialty score higher (f_skill) but others still fill the list
    candidates = [cg for cg in pool if _role_ok(cg, care)]
    physio = any(h.id == "physiotherapy" for h in ex.services)
    if physio:
        candidates = [cg for cg in candidates if _specialty_ok(cg, "physiotherapy")] or candidates

    scored: list[Match] = []
    for cg in candidates:
        dist = (haversine_km(location[0], location[1], cg.lat, cg.lng)
                if location and cg.lat is not None and cg.lng is not None else None)
        slot = next_free(cg.slots, ref)
        wait_h = (slot - ref).total_seconds() / 3600 if slot else None

        f_time = 0.0 if wait_h is None else max(0.0, 1 - wait_h / window_h) if wait_h <= window_h else 0.0
        if mode == "home":
            f_dist = 0.5 if dist is None else max(0.0, 1 - dist / config.MAX_HOME_VISIT_KM)
        elif mode == "specialist":
            f_dist = 0.5 if dist is None else max(0.0, 1 - dist / 30)
        else:
            f_dist = 0.0
        spoken = [l for l in want_langs if l in cg.languages]
        f_lang = 1.0 if spoken and spoken[0] == want_langs[0] else 0.6 if spoken else 0.2
        bayes = ((cg.rating or 4.0) * cg.rating_count + 4.2 * 10) / (cg.rating_count + 10)
        f_rating = min(1.0, max(0.0, (bayes - 3.5) / 1.5))
        matched_skills = [s for s in want_skills if any(s in k or k in s for k in cg.skills)]
        f_skill = 1.0 if not want_skills else len(matched_skills) / len(want_skills)
        wrong_specialty = care == "specialist" and not _specialty_ok(cg, specialty)
        if care == "specialist":
            f_skill = 0.3 if wrong_specialty else 1.0
        if want_female:
            f_skill = (f_skill + (1.0 if cg.gender in ("female", "f") else 0.0)) / 2

        score = sum(w[k] * v for k, v in
                    {"skill": f_skill, "time": f_time, "distance": f_dist, "language": f_lang, "rating": f_rating}.items())
        if mode == "home" and dist is not None and dist > config.MAX_HOME_VISIT_KM:
            score *= 0.5  # outside the home-visit radius: only if nobody closer
        if wrong_specialty:
            score *= 0.5  # another specialty: only fills the list after the right ones
        if slot is None:
            score *= 0.5  # no free slot listed: shown last, not hidden

        en_slot, hl_slot, hi_slot = _slot_labels(slot, ref)
        lang = spoken[0] if spoken else (cg.languages[0] if cg.languages else None)
        female = cg.gender in ("female", "f")
        parts_en, parts_hl, parts_hi = [], [], []
        if lang:
            parts_en.append(f"{lang}-speaking")
            parts_hl.append(f"{lang} {'bolti' if female else 'bolte'} hain")
            parts_hi.append(f"{LANG_HI.get(lang, lang)} {'बोलती' if female else 'बोलते'} हैं")
        if mode != "tele" and dist is not None:
            parts_en.append(f"{dist:.1f} km away")
            parts_hl.append(f"{dist:.1f} km door")
            parts_hi.append(f"{dist:.1f} किमी दूर")
        if slot:
            if mode == "tele":
                parts_en.append(f"video call free {'at ' if (slot.date() == ref.date()) else ''}{en_slot}")
                parts_hl.append(f"video call {hl_slot} free")
                parts_hi.append(f"वीडियो कॉल {hi_slot} खाली")
            else:
                parts_en.append(f"free {'at ' if (slot.date() == ref.date()) else ''}{en_slot}")
                parts_hl.append(f"{hl_slot} free")
                parts_hi.append(f"{hi_slot} खाली")
        else:
            parts_en.append("no free slot listed")
            parts_hl.append("abhi koi free slot nahi")
            parts_hi.append("अभी कोई खाली समय नहीं")
        if wrong_specialty:
            other = cg.specialty or cg.role
            parts_en.append(f"other department ({other})")
            parts_hl.append(f"doosra vibhag ({other})")
            parts_hi.append(f"दूसरा विभाग ({other})")
        if matched_skills:
            parts_en.append(f"{matched_skills[0]} experience")
            parts_hl.append(f"{matched_skills[0]} ka anubhav")
            parts_hi.append(f"{matched_skills[0]} का अनुभव")
        local = {"hi": parts_hi, "hinglish": parts_hl}.get(ex.language, parts_en)
        scored.append(Match(
            caregiver=cg, score=round(score, 2), distance_km=None if dist is None else round(dist, 1),
            next_slot=slot, reason=", ".join(parts_en), reason_local=", ".join(local),
            slot_label=en_slot, slot_label_local={"hi": hi_slot, "hinglish": hl_slot}.get(ex.language, en_slot),
            features={"skill": round(f_skill, 2), "time": round(f_time, 2), "distance": round(f_dist, 2),
                      "language": round(f_lang, 2), "rating": round(f_rating, 2)},
        ))
    far = timedelta(days=3650)
    scored.sort(key=lambda m: (-m.score, (m.next_slot - ref) if m.next_slot else far,
                               m.distance_km if m.distance_km is not None else 1e9))
    return scored[:top_k]

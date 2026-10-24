"""Caregiver ranking: the organisers' reference recipe (data/sanocare_v1/README.md, "How
matched_caregivers.score was generated"), with the details fitted against their 340 labelled
rows. scripts/eval_matching.py reproduces every label's caregivers and scores.

Eligible: the role for the care type (medic: home visit and home nursing, phlebotomist: lab
test, doctor: teleconsultation), active, holding the skill the request needs (a Medic visit
needs vitals_monitoring; home nursing needs the procedure asked for, e.g. injection_im or
wound_dressing), and, for home visits, the request inside the caregiver's max_radius_km.
Nobody eligible gives an empty list, as in the labels.

    score = 0.35 language + 0.30 proximity + 0.20 skill + 0.15 rating
            summed in that order, rounded to 2 decimals, capped at 0.99

    language   1 if the caregiver speaks the request's language. Hindi counts for every
               request: the labels give Hindi-only caregivers full credit on English requests.
    proximity  1 - distance / service radius, where the service radius is the largest
               max_radius_km in the roster (12 km; MAX_HOME_VISIT_KM when no radius is given).
               Teleconsultation ignores distance (1).
    skill      share of the needed skills the caregiver has. The main one is also an
               eligibility rule, so this is 1 in every labelled row.
    rating     (rating - lowest) / (highest - lowest) over the roster (3.8 to 5.0).

Order: rounded score, ties in roster order. We return the top 3; each label keeps the first
1, 2 or 3 of that list (chosen at random), so a label is always a prefix of our list.
Availability is shown, not scored: the labels do not use it.

Reasons are built only from computed facts, in the labels' style: "Hindi-speaking, 2.7 km
away, free 15:00–21:00" and, for teleconsultation, "Hindi-speaking, free 13:00–16:00, ★4.9".
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

from .. import config
from ..nlp.extract import Extraction
from .caregivers import Caregiver, load, next_free, now

# README order; the order of the sum matters for how a few scores round
WEIGHTS = {"language": 0.35, "distance": 0.30, "skill": 0.20, "rating": 0.15}
SCORE_CAP = 0.99
SHARED_LANGUAGE = "Hindi"
LANGUAGE_WORDS = {"hindi", "english", "punjabi", "urdu", "bengali", "bangla", "tamil", "telugu", "malayalam",
                  "marathi", "gujarati", "kannada", "bhojpuri", "odia", "konkani", "haryanvi"}
FEMALE_WORDS = {"lady", "ladies", "female", "mahila", "woman", "aurat"}
LANG_HI = {"Hindi": "हिंदी", "English": "अंग्रेज़ी", "Punjabi": "पंजाबी", "Urdu": "उर्दू", "Tamil": "तमिल",
           "Malayalam": "मलयालम", "Bengali": "बंगाली", "Telugu": "तेलुगु", "Marathi": "मराठी",
           "Bhojpuri": "भोजपुरी", "Konkani": "कोंकणी", "Gujarati": "गुजराती", "Kannada": "कन्नड़",
           "Haryanvi": "हरियाणवी"}

# Skill names as the organisers' roster writes them, with the spellings other files (the
# dev sample, our lexicon's service skills) use for the same thing.
SKILL_SYNONYMS = {
    "injection_im": ("injection", "injections", "im injection", "intramuscular injection"),
    "injection_iv": ("iv", "iv injection", "iv drip", "drip", "iv cannulation", "cannula"),
    "wound_dressing": ("wound care", "dressing", "bedsore care", "bedsore", "wound"),
    "catheter_care": ("catheter",),
    "post_surgical_care": ("post operative care", "post op care", "post surgery care", "post-operative care"),
    "elderly_care": ("geriatric care", "elder care"),
    "vitals_monitoring": ("vitals check", "vitals", "vital signs", "vitals monitor"),
    "bp_sugar_check": ("bp check", "sugar check", "bp and sugar check"),
    "nebulization": ("nebulisation", "nebuliser", "nebulizer"),
    "sample_collection": ("home phlebotomy", "phlebotomy", "blood collection"),
    "vaccination": ("vaccine", "immunisation", "immunization"),
    "teleconsultation": ("teleconsult", "video consult", "online consult"),
    "physiotherapy": ("physio",),
}
VISIT_SKILL = "vitals_monitoring"            # every reference Medic visit (paramedic_home_visit) needs it
CONTEXT_SKILLS = {"post_surgical_care", "elderly_care"}  # needed only when no procedure is named
ALSO_SATISFIES = {"vaccination": {"injection_im"}}       # an IM-injection skill covers a vaccine

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


def _skill_key(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", s.strip().lower())


_SKILL_LOOKUP = {_skill_key(alias): key for key, aliases in SKILL_SYNONYMS.items() for alias in (key, *aliases)}


def canonical_skill(s: str) -> str:
    """"vitals check", "Wound care", "injection_im" -> the roster's name for the skill."""
    k = _skill_key(s)
    return _SKILL_LOOKUP.get(k, k.replace(" ", "_"))


def _has_skill(skills: set[str], need: str) -> bool:
    return need in skills or bool(ALSO_SATISFIES.get(need, set()) & skills)


def _role_ok(cg: Caregiver, care: str) -> bool:
    roles = config.ROLES_FOR_CARE.get(care, [])
    # whole words: "medic" (the organisers' home-visit role) must not match "paramedic"
    if any(r == cg.role or re.search(r"\b" + re.escape(r) + r"\b", cg.role) for r in roles):
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
    """Languages that count as a match, best first: the ones the user names, else the
    request's language plus Hindi (shared by everyone in the reference labels)."""
    asked = [t.title() for t in ex.tokens if t in LANGUAGE_WORDS]
    if asked:
        return list(dict.fromkeys(asked))
    return ["English", SHARED_LANGUAGE] if ex.language == "en" else [SHARED_LANGUAGE]


def needed_skills(ex: Extraction, care: str, specialty: str | None = None) -> list[str]:
    """Skills (roster names) this request needs; the first is required, the rest add to the
    skill score. A Medic visit needs vitals monitoring whatever the symptom; home nursing
    needs the procedures named (dressing, injection, IV, catheter...), or the care context
    (post-operative, elderly) when no procedure is named. Lab tests and doctor consults:
    the role is enough."""
    if care == "paramedic":
        return [VISIT_SKILL]
    if care != "nurse":
        return []
    asked = list(dict.fromkeys(canonical_skill(h.entry.meta["skill"]) for h in ex.services
                               if h.entry.meta.get("skill")))
    if "injection_iv" in asked and "injection_im" in asked:  # "IV injection" is one IV procedure
        asked.remove("injection_im")
    procedures = [s for s in asked if s not in CONTEXT_SKILLS]
    return procedures or asked[:1]


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


def _free_parts(cg: Caregiver, slot: datetime | None, ref: datetime) -> tuple[str, str, str]:
    """"free 11:00–19:00" (the roster's window today), else the next listed start in 24h time."""
    if cg.window:
        return f"free {cg.window}", f"{cg.window} free", f"{cg.window} खाली"
    if slot is None:
        return "no free slot listed", "abhi koi free slot nahi", "अभी कोई खाली समय नहीं"
    hm = f"{slot.hour:02d}:{slot.minute:02d}"
    days = (slot.date() - ref.date()).days
    if days <= 0:
        return f"free {hm}", f"aaj {hm} se free", f"आज {hm} से खाली"
    if days == 1:
        return f"free tomorrow {hm}", f"kal {hm} se free", f"कल {hm} से खाली"
    wd = slot.strftime("%a")
    return f"free {wd} {hm}", f"{wd} {hm} se free", f"{wd} {hm} से खाली"


def rank(care: str, urgency: str, ex: Extraction, location: tuple[float, float] | None,
         specialty: str | None = None, top_k: int | None = None,
         caregivers: list[Caregiver] | None = None, ref: datetime | None = None) -> list[Match]:
    """Top caregivers for a decided care type. `urgency` does not change the reference
    ranking; `ref` (default: now) only sets the next free slot shown."""
    if care == "emergency":
        return []
    top_k = top_k or config.TOP_K
    pool = caregivers if caregivers is not None else load()[0]
    ref = ref or now()
    physio = any(h.id == "physiotherapy" for h in ex.services)
    # doctors are virtual: a GP or specialist consult is a teleconsultation (physiotherapy visits)
    tele = care in config.TELE_CARE or (care == "specialist" and not physio)
    want_langs = preferred_languages(ex)
    want_skills = needed_skills(ex, care, specialty)
    want_female = any(t in FEMALE_WORDS for t in ex.tokens)

    # roster-wide scales: the rating range and the largest service radius
    ratings = [cg.rating for cg in pool if cg.rating is not None]
    r_lo, r_hi = (min(ratings), max(ratings)) if ratings else (0.0, 0.0)
    radii = [cg.radius_km for cg in pool if cg.radius_km]
    service_km = max(radii) if radii else config.MAX_HOME_VISIT_KM

    if care == "specialist":
        candidates = [cg for cg in pool if _role_ok(cg, "specialist")]
        if physio:
            candidates = [cg for cg in candidates if _specialty_ok(cg, "physiotherapy")] or candidates
        gp_standin = not candidates  # no specialists on the roster: its (virtual) doctors take the consult
        if gp_standin:
            candidates = [cg for cg in pool if _role_ok(cg, "gp")]
    else:
        candidates = [cg for cg in pool if _role_ok(cg, care)]
        gp_standin = False

    scored: list[Match] = []
    for cg in candidates:
        if not cg.active:
            continue
        skills = {canonical_skill(s) for s in cg.skills}
        if skills and want_skills and not _has_skill(skills, want_skills[0]):
            continue  # the main skill the request needs is a hard requirement
        dist = (haversine_km(location[0], location[1], cg.lat, cg.lng)
                if location and cg.lat is not None and cg.lng is not None else None)
        if not tele and dist is not None and dist > (cg.radius_km or config.MAX_HOME_VISIT_KM):
            continue  # outside the area this caregiver serves

        spoken = [lang for lang in want_langs if lang in cg.languages]
        f_lang = 1.0 if spoken else 0.5 if not cg.languages else 0.0
        if tele:
            f_dist = 1.0
        else:
            f_dist = 0.5 if dist is None else max(0.0, 1 - dist / service_km)
        if not want_skills:
            f_skill = 1.0
        elif not skills:
            f_skill = 0.5  # skills not listed: unknown
        else:
            f_skill = sum(_has_skill(skills, s) for s in want_skills) / len(want_skills)
        wrong_specialty = care == "specialist" and not gp_standin and not _specialty_ok(cg, specialty)
        if care == "specialist" and specialty:
            f_skill = 0.5 if gp_standin else 0.0 if wrong_specialty else 1.0
        female = cg.gender in ("female", "f")
        if want_female:
            f_skill = (f_skill + (1.0 if female else 0.0)) / 2
        if cg.rating is None:
            f_rating = 0.5
        elif r_hi > r_lo:
            f_rating = min(1.0, max(0.0, (cg.rating - r_lo) / (r_hi - r_lo)))
        else:
            f_rating = 1.0

        feats = {"language": f_lang, "distance": f_dist, "skill": f_skill, "rating": f_rating}
        score = min(SCORE_CAP, round(sum(WEIGHTS[k] * v for k, v in feats.items()), 2))

        slot = next_free(cg.slots, ref)
        en_slot, hl_slot, hi_slot = _slot_labels(slot, ref)
        lang = spoken[0] if spoken else (cg.languages[0] if cg.languages else None)
        parts_en, parts_hl, parts_hi = [], [], []
        if lang:
            parts_en.append(f"{lang}-speaking")
            parts_hl.append(f"{lang} {'bolti' if female else 'bolte'} hain")
            parts_hi.append(f"{LANG_HI.get(lang, lang)} {'बोलती' if female else 'बोलते'} हैं")
        if not tele and dist is not None:
            parts_en.append(f"{dist:.1f} km away")
            parts_hl.append(f"{dist:.1f} km door")
            parts_hi.append(f"{dist:.1f} किमी दूर")
        for parts, text in zip((parts_en, parts_hl, parts_hi), _free_parts(cg, slot, ref)):
            parts.append(text)
        if tele and cg.rating is not None:
            for parts in (parts_en, parts_hl, parts_hi):
                parts.append(f"★{cg.rating:.1f}")
        if wrong_specialty and specialty:
            other = cg.specialty or cg.role
            parts_en.append(f"other department ({other})")
            parts_hl.append(f"doosra vibhag ({other})")
            parts_hi.append(f"दूसरा विभाग ({other})")
        local = {"hi": parts_hi, "hinglish": parts_hl}.get(ex.language, parts_en)
        scored.append(Match(
            caregiver=cg, score=score, distance_km=None if dist is None else round(dist, 1),
            next_slot=slot, reason=", ".join(parts_en), reason_local=", ".join(local),
            slot_label=en_slot, slot_label_local={"hi": hi_slot, "hinglish": hl_slot}.get(ex.language, en_slot),
            features={k: round(v, 2) for k, v in feats.items()},
        ))
    scored.sort(key=lambda m: -m.score)  # stable: ties keep roster order, as in the labels
    return scored[:top_k]

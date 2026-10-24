"""Labels, thresholds and paths in one place.

Outward-facing labels follow the organisers' dataset (Sanocare synthetic care-triage
dataset v1, data/sanocare_v1/README.md) and live here and nowhere else.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
DATA_DIR = APP_DIR / "data"
PROVIDED_DIR = REPO_DIR / "data" / "provided"  # organiser files go here (git-ignored)
ORG_DATA_DIR = REPO_DIR / "data" / "sanocare_v1"  # the organisers' dataset (synthetic, redistributable)
MODELS_DIR = REPO_DIR / "models"

VERSION = "0.1.0"

# Internal care keys -> API values (the organisers' enum). Doctors are virtual in their
# roster, so a specialist need is a teleconsultation (the department travels in the trace).
CARE_TYPES: dict[str, str] = {
    "paramedic": "paramedic_home_visit",
    "nurse": "home_nursing",
    "lab": "lab_test_home",
    "gp": "teleconsultation",
    "specialist": "teleconsultation",
    "emergency": "emergency_112",
}

# Internal urgency keys -> API values, lowest to highest.
URGENCY: dict[str, str] = {
    "routine": "scheduled",
    "same_day": "same_day",
    "immediate": "emergency",
}
URGENCY_ORDER = list(URGENCY)  # ["routine", "same_day", "immediate"]

# Urgency that goes with each non-emergency care type in the organisers' labels: home
# visits, nursing and doctor consults the same day, home lab tests scheduled.
CARE_URGENCY: dict[str, str] = {"paramedic": "same_day", "nurse": "same_day", "gp": "same_day",
                                "specialist": "same_day", "lab": "routine"}

# Our red-flag ids -> the organisers' controlled vocabulary, where one exists. Flags with
# no counterpart there (poisoning, burns, major injury...) keep our id.
RED_FLAG_API: dict[str, str] = {
    "chest_pain": "chest_pain",
    "breathing_difficulty": "breathlessness",
    "unconscious": "unconsciousness",
    "severe_bleeding": "severe_bleeding",
    "stroke_signs": "stroke_symptoms",
    "seizure": "seizure",
    "infant_danger_sign": "high_fever_infant",
    "self_harm_risk": "suicidal_ideation",
    "severe_dehydration": "severe_dehydration",
}

# Extra spellings we accept when reading labelled files (lower-cased).
LABEL_ALIASES: dict[str, str] = {
    # earlier API values (before the organisers' enum)
    "nurse": "nurse",
    "gp_teleconsult": "gp",
    "emergency_referral": "emergency",
    "lab test home": "lab",
    "lab": "lab",
    "teleconsultation": "gp",
    "home nursing": "nurse",
    "routine": "routine",
    "immediate": "immediate",
    "scheduled": "routine",
    "paramedic home visit": "paramedic",
    "paramedic_visit": "paramedic",
    "nurse visit": "nurse",
    "nurse home visit": "nurse",
    "nurse_home_visit": "nurse",
    "home nurse": "nurse",
    "specialist consult": "specialist",
    "specialist_consult": "specialist",
    "gp": "gp",
    "gp teleconsult": "gp",
    "teleconsult": "gp",
    "specialist": "specialist",
    "specialist referral": "specialist",
    "emergency": "emergency",
    "emergency referral": "emergency",
    "same-day": "same_day",
    "same day": "same_day",
    "emergency_immediate": "immediate",
}

# Caregiver roles that can serve each care type (matched case-insensitively).
# ("medic" is the organisers' home-visit role: GNM / B.Sc Nursing, does visits and nursing)
ROLES_FOR_CARE: dict[str, list[str]] = {
    "paramedic": ["paramedic", "emt", "health worker", "medic"],
    "nurse": ["nurse", "staff nurse", "nursing", "medic"],
    "lab": ["phlebotomist", "lab technician", "sample collector", "lab"],
    "gp": ["gp", "general physician", "doctor", "physician", "family doctor", "general practitioner",
           "mbbs", "medical officer"],
    "specialist": ["specialist", "consultant", "physiotherapist", "psychologist"],
    "emergency": [],
}
TELE_CARE = {"gp"}  # no home visit, so distance does not count

# Follow-up questions.
MAX_FOLLOWUPS = int(os.getenv("CC_MAX_FOLLOWUPS", "3"))
FOLLOWUP_POLICY = os.getenv("CC_FOLLOWUP_POLICY", "minimal")  # minimal | safety

# Matching.
TOP_K = int(os.getenv("CC_TOP_K", "3"))
MAX_HOME_VISIT_KM = float(os.getenv("CC_MAX_HOME_VISIT_KM", "15"))
SAME_DAY_WINDOW_H = 12.0
ROUTINE_WINDOW_H = 72.0

# Language of the API `reasoning` / `reason` strings: "en" (as in the indicative
# example) or "user" (reply in the user's language). The UI always gets both.
REASONING_LANGUAGE = os.getenv("CC_REASONING_LANGUAGE", "en")

# Fixed "now" for reproducible evaluation, e.g. 2026-10-24T11:00:00+05:30.
NOW_OVERRIDE = os.getenv("CC_NOW")
TIMEZONE = os.getenv("CC_TZ", "Asia/Kolkata")

CAREGIVERS_PATH = os.getenv("CC_CAREGIVERS")  # else data/provided/caregivers.*, then data/sanocare_v1, then the dev sample

# Call-for-help numbers shown on every emergency.
EMERGENCY_NUMBERS = [
    {"label": "Emergency (all India)", "label_hi": "Emergency (poore Bharat mein)", "number": "112"},
    {"label": "Ambulance in Delhi (CATS, free)", "label_hi": "Delhi ambulance (CATS, free)", "number": "102"},
    {"label": "Ambulance in many states", "label_hi": "Kai rajyon mein ambulance", "number": "108"},
]
FLAG_HELPLINES = {
    "self_harm_risk": {"label": "Tele-MANAS mental health helpline", "label_hi": "Tele-MANAS helpline", "number": "14416"},
    "psychiatric_emergency": {"label": "Tele-MANAS mental health helpline", "label_hi": "Tele-MANAS helpline",
                              "number": "14416"},
    "poisoning": {"label": "AIIMS Poisons Information Centre", "label_hi": "AIIMS zeher helpline", "number": "1800-116-117"},
}


def api_care(key: str | None) -> str | None:
    return CARE_TYPES.get(key, key) if key else None


def api_urgency(key: str | None) -> str | None:
    return URGENCY.get(key, key) if key else None


def api_flags(flags: list[str]) -> list[str]:
    return list(dict.fromkeys(RED_FLAG_API.get(f, f) for f in flags))


def internal_label(value: str | None) -> str | None:
    """Map an API value, alias or internal key back to the internal key."""
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    low = v.lower()
    for key, api in CARE_TYPES.items():
        if low in (key, api.lower()):
            return key
    for key, api in URGENCY.items():
        if low in (key, api.lower()):
            return key
    return LABEL_ALIASES.get(low.replace("_", " "), LABEL_ALIASES.get(low, low))


def internal_care(value: str | None) -> str | None:
    """A care-type label (API value, old value or alias) as an internal key; specialist and
    GP both mean a doctor consult."""
    key = internal_label(value)
    return "gp" if key == "specialist" else key


def internal_urgency(value: str | None) -> str | None:
    """An urgency label as an internal key ("emergency" here means immediate)."""
    if value is None or not str(value).strip():
        return None
    low = str(value).strip().lower()
    for key, api in URGENCY.items():
        if low in (key, api.lower()):
            return key
    return internal_label(value)


def urgency_rank(key: str | None) -> int:
    return URGENCY_ORDER.index(key) if key in URGENCY_ORDER else -1

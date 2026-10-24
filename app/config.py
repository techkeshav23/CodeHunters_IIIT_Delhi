"""Labels, thresholds and paths in one place.

The organisers publish the final JSON schema with the dataset. Only
`paramedic_home_visit` and `same_day` are confirmed by the indicative schema,
so every outward-facing label lives here and nowhere else.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
DATA_DIR = APP_DIR / "data"
PROVIDED_DIR = REPO_DIR / "data" / "provided"  # organiser files go here (git-ignored)
MODELS_DIR = REPO_DIR / "models"

VERSION = "0.1.0"

# Internal care keys -> API values. No final schema was published, so these follow
# the problem statement's own wording ("Paramedic home visit, nurse, GP teleconsult,
# specialist, or emergency referral"); only paramedic_home_visit appears in its example.
CARE_TYPES: dict[str, str] = {
    "paramedic": "paramedic_home_visit",
    "nurse": "nurse",
    "gp": "gp_teleconsult",
    "specialist": "specialist",
    "emergency": "emergency_referral",
}

# Internal urgency keys -> API values, lowest to highest.
URGENCY: dict[str, str] = {
    "routine": "routine",
    "same_day": "same_day",
    "immediate": "immediate",
}
URGENCY_ORDER = list(URGENCY)  # ["routine", "same_day", "immediate"]

# Extra spellings we accept when reading labelled files (lower-cased).
LABEL_ALIASES: dict[str, str] = {
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
ROLES_FOR_CARE: dict[str, list[str]] = {
    "paramedic": ["paramedic", "emt", "health worker"],
    "nurse": ["nurse", "staff nurse", "nursing"],
    "gp": ["gp", "general physician", "doctor", "physician", "family doctor"],
    "specialist": ["specialist", "consultant", "physiotherapist", "psychologist"],
    "emergency": [],
}
TELE_CARE = {"gp"}  # no home visit, so distance barely matters

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

CAREGIVERS_PATH = os.getenv("CC_CAREGIVERS")  # default: data/provided/caregivers.* else dev sample

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


def urgency_rank(key: str | None) -> int:
    return URGENCY_ORDER.index(key) if key in URGENCY_ORDER else -1

"""The learned care-type model (trained by scripts/train_triage.py on the organisers'
dataset) and how its answer is combined with the rules.

Every request goes through the model. It predicts one of paramedic, nurse, lab, gp,
emergency or "followup" (not enough to decide) from:
- the normalised tokens the rules see (Devanagari, Hinglish and English spellings meet),
- what the lexicon recognised: services, symptoms and red flags as tags (SVC_injection...).

Safety: red-flag rules run first and always win; the model can add an emergency
(P >= `emergency_threshold`) but never remove one. The final care type blends the
model's probabilities with the rules' choice (weight `rules_weight`, picked on
validation folds); urgency then follows the care type (config.CARE_URGENCY) and is
never lower than the rules' own urgency.

Settings come from models/triage_meta.json and can be overridden with CC_RULES_WEIGHT
and CC_EMERGENCY_THRESHOLD. CC_MODEL=off runs on rules only.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..config import CARE_URGENCY, MODELS_DIR, URGENCY_ORDER, urgency_rank
from ..nlp.extract import Extraction, extract
from ..nlp.normalize import BOUNDARY

log = logging.getLogger(__name__)

MODEL_PATH = Path(os.getenv("CC_MODEL_PATH", str(MODELS_DIR / "triage.joblib")))
DEFAULTS = {"rules_weight": 0.3, "emergency_threshold": 0.5}
FOLLOWUP = "followup"


def features_text(text: str, ex: Extraction | None = None) -> str:
    """Normalised tokens plus tags for what the lexicon recognised."""
    ex = ex or extract(text)
    words = " ".join("." if t == BOUNDARY else t for t in ex.tokens)
    tags = ([f"SVC_{h.id}" for h in ex.services] + [f"SYM_{h.id}" for h in ex.symptoms]
            + [f"FLAG_{h.id}" for h in ex.red_flags])
    if ex.age_group:
        tags.append(f"AGE_{ex.age_group}")
    if not ex.services and not ex.symptoms and not ex.red_flags:
        tags.append("NOTHING_KNOWN")
    return words + " | " + " ".join(tags)


@dataclass
class Model:
    bundle: dict
    settings: dict
    meta: dict

    def probs(self, text: str, ex: Extraction | None = None) -> dict[str, float]:
        x = self.bundle["vectorizer"].transform([features_text(text, ex)])
        clf = self.bundle["care_clf"]
        return {str(k): float(v) for k, v in zip(clf.classes_, clf.predict_proba(x)[0])}


def settings_from(meta: dict | None) -> dict:
    s = dict(DEFAULTS)
    s.update({k: v for k, v in (meta or {}).get("settings", {}).items() if k in DEFAULTS})
    for key, env in (("rules_weight", "CC_RULES_WEIGHT"), ("emergency_threshold", "CC_EMERGENCY_THRESHOLD")):
        if os.getenv(env):
            s[key] = float(os.environ[env])
    return s


@lru_cache(maxsize=1)
def get_model() -> Model | None:
    if os.getenv("CC_MODEL", "on").lower() == "off" or not MODEL_PATH.exists():
        return None
    import joblib

    meta_path = MODEL_PATH.with_name(MODEL_PATH.stem + "_meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    source = str((meta or {}).get("source", "")).lower()
    if not source or "smoke" in source:  # a model with no record of its training data stays off
        log.warning("not loading %s: training source is %r", MODEL_PATH, source or "unknown")
        return None
    bundle = joblib.load(MODEL_PATH)
    return Model(bundle=bundle, settings=settings_from(meta), meta=meta or {})


def blend_care(model_probs: dict[str, float], rules_care: str | None, rules_weight: float) -> dict[str, float]:
    """Model probabilities mixed with a one-hot vote for the rules' choice. When the rules
    understood nothing, the model alone decides (including "followup": ask first)."""
    if not rules_care:
        return dict(model_probs)
    keys = set(model_probs) | {rules_care}
    return {k: (1 - rules_weight) * model_probs.get(k, 0.0) + rules_weight * (1.0 if k == rules_care else 0.0)
            for k in keys}


def fuse(model_probs: dict[str, float], rules_care: str | None, settings: dict) -> tuple[str, float]:
    """The care type (or "followup") and its blended probability. "emergency" is left out
    here: a model emergency is raised separately, only above its threshold."""
    rules_care = "gp" if rules_care == "specialist" else rules_care
    blended = blend_care({k: v for k, v in model_probs.items() if k != "emergency"}, rules_care,
                         settings["rules_weight"])
    blended.pop("emergency", None)
    care = max(blended, key=blended.get)
    return care, blended[care]


def care_urgency(care: str, rules_urgency: str | None) -> str:
    """Urgency for a non-emergency care type: the organisers' policy for that care type,
    never lower than what the rules found (a baby, an older adult, severe pain)."""
    default = CARE_URGENCY.get(care, "same_day")
    if rules_urgency in URGENCY_ORDER and urgency_rank(rules_urgency) > urgency_rank(default):
        return rules_urgency
    return default

"""Optional learned model (trained by scripts/train_baseline.py on the doctor-labelled
train set) and how it is blended with the rules.

- Red-flag rules always win: the model can add emergencies, never remove them.
- Care type: blend of model probabilities and the rules' choice (weight `rules_weight`).
- Urgency: cost-sensitive choice; under-triage costs `under_cost` times more than over-triage.
- Emergency: the model can raise one when P(emergency) >= `emergency_threshold`.

Settings come from models/baseline_meta.json (written by the trainer) and can be
overridden with CC_RULES_WEIGHT, CC_UNDER_COST, CC_EMERGENCY_THRESHOLD.
Set CC_MODEL=off to run on rules only.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..config import MODELS_DIR, URGENCY_ORDER
from ..nlp.lexicon import get_lexicon
from ..nlp.normalize import BOUNDARY, analyse

MODEL_PATH = Path(os.getenv("CC_MODEL_PATH", str(MODELS_DIR / "baseline.joblib")))
DEFAULTS = {"rules_weight": 0.35, "under_cost": 3.0, "emergency_threshold": 0.35}


def features_text(text: str) -> str:
    """The same normalised tokens the rules see, so Hindi script, Hinglish and
    spelling variants share features."""
    lex = get_lexicon()
    toks = lex.canon_tokens(analyse(text).tokens)
    return " ".join("." if t == BOUNDARY else t for t in toks)


@dataclass
class Model:
    bundle: dict
    settings: dict

    def probs(self, text: str) -> tuple[dict[str, float], dict[str, float]]:
        x = self.bundle["vectorizer"].transform([features_text(text)])
        care = dict(zip(self.bundle["care_clf"].classes_, self.bundle["care_clf"].predict_proba(x)[0]))
        urg = dict(zip(self.bundle["urgency_clf"].classes_, self.bundle["urgency_clf"].predict_proba(x)[0]))
        return {k: float(v) for k, v in care.items()}, {k: float(v) for k, v in urg.items()}


def settings_from(meta: dict | None) -> dict:
    s = dict(DEFAULTS)
    s.update({k: v for k, v in (meta or {}).get("settings", {}).items() if k in DEFAULTS})
    for key, env in (("rules_weight", "CC_RULES_WEIGHT"), ("under_cost", "CC_UNDER_COST"),
                     ("emergency_threshold", "CC_EMERGENCY_THRESHOLD")):
        if os.getenv(env):
            s[key] = float(os.environ[env])
    return s


@lru_cache(maxsize=1)
def get_model() -> Model | None:
    if os.getenv("CC_MODEL", "on").lower() == "off" or not MODEL_PATH.exists():
        return None
    import joblib

    bundle = joblib.load(MODEL_PATH)
    meta_path = MODEL_PATH.with_name(MODEL_PATH.stem + "_meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    return Model(bundle=bundle, settings=settings_from(meta))


def blend_care(model_probs: dict[str, float], rules_care: str | None, rules_weight: float) -> dict[str, float]:
    keys = set(model_probs) | ({rules_care} if rules_care else set())
    w = rules_weight if rules_care else 0.0
    return {k: (1 - w) * model_probs.get(k, 0.0) + w * (1.0 if k == rules_care else 0.0) for k in keys}


def choose_urgency(probs: dict[str, float], under_cost: float) -> str:
    """Minimise expected cost; predicting below the true level costs `under_cost` per step."""
    levels = [u for u in URGENCY_ORDER if u in probs] or URGENCY_ORDER
    best, best_cost = levels[0], float("inf")
    for pred in levels:
        cost = 0.0
        for true, p in probs.items():
            if true not in URGENCY_ORDER:
                continue
            gap = URGENCY_ORDER.index(true) - URGENCY_ORDER.index(pred)
            cost += p * (under_cost * gap if gap > 0 else -gap)
        if cost < best_cost:
            best, best_cost = pred, cost
    return best

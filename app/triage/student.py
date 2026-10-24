"""The fine-tuned triage model ("student"): MuRIL, multi-task, served with ONNX Runtime.

Trained by scripts/train_student.py on messages written for us by Claude (the teacher,
scripts/gen_data.py) with labels fixed by docs/LABELING_GUIDE.md; the organisers' 340
rows are kept out of training and used as the test set.

One forward pass gives five heads:
- care     paramedic, nurse, lab, gp, emergency, followup, out_of_scope
- urgency  routine, same_day, immediate
- flags    the organisers' 9 red flags + other_emergency (independent sigmoids)
- tags     symptoms and services mentioned (Module 1's "structured symptoms")
- who      self, adult, elderly, child, infant, pregnant, unknown

Care and urgency probabilities are temperature-calibrated on held-out case families
(meta.json), so "0.9" means about 9 in 10 such answers are right on that data.

Files (models/student/): model.onnx (int8), tokenizer.json, meta.json. If they are
missing, get_student() returns None and the pipeline falls back to rules + the old model.
CC_STUDENT=off disables it.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..config import MODELS_DIR

log = logging.getLogger(__name__)

STUDENT_DIR = Path(os.getenv("CC_STUDENT_DIR", str(MODELS_DIR / "student")))
HEADS = ("care", "urgency", "flags", "tags", "who")
MULTI_LABEL = ("flags", "tags")


def compose(text: str, history: list[tuple[str, str]] | None = None) -> str:
    """The model's input: the conversation so far, newest last. The same function is
    used in training (scripts/train_student.py) and serving."""
    parts = [f"{'bot' if role == 'assistant' else 'user'}: {t.strip()}" for role, t in (history or []) if t and t.strip()]
    parts.append(f"user: {(text or '').strip()}")
    return " | ".join(parts)


def _softmax(x: np.ndarray, t: float = 1.0) -> np.ndarray:
    z = x / max(t, 1e-3)
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class StudentOutput:
    care: dict[str, float]
    urgency: dict[str, float]
    flags: dict[str, float]
    tags: dict[str, float]
    who: dict[str, float]
    confidence: float  # calibrated probability of the top care class
    band: str  # "high" | "medium" | "low"
    latency_ms: float
    thresholds: dict = field(default_factory=dict)

    @property
    def top_care(self) -> str:
        return max(self.care, key=self.care.get)

    @property
    def top_urgency(self) -> str:
        return max(self.urgency, key=self.urgency.get)

    @property
    def top_who(self) -> str:
        return max(self.who, key=self.who.get)

    def flags_on(self) -> list[str]:
        t = self.thresholds.get("flag", 0.5)
        return [k for k, v in sorted(self.flags.items(), key=lambda kv: -kv[1]) if v >= t]

    def tags_on(self) -> list[str]:
        t = self.thresholds.get("tag", 0.5)
        return [k for k, v in sorted(self.tags.items(), key=lambda kv: -kv[1]) if v >= t]

    @property
    def says_emergency(self) -> bool:
        """Emergency when a red-flag head names a danger sign. The care head's "emergency"
        class alone is not enough: on long English questions (CARE-Bench) it fired on a third of
        the non-urgent cases, while requiring a named sign kept recall at 1.0 on every test set
        and cut false alarms to 0% (our hard cases) and 13.8% (CARE-Bench)."""
        return bool(self.flags_on())


class Student:
    def __init__(self, folder: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        self.labels: dict[str, list[str]] = self.meta["heads"]
        self.max_len = int(self.meta.get("max_len", 160))
        self.thresholds = self.meta.get("thresholds", {})
        self.temperature = self.meta.get("temperature", {})
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tok.no_truncation()
        self.tok.no_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.getenv("CC_STUDENT_THREADS", "2"))
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(folder / "model.onnx"), so, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.sess.get_inputs()}
        self.cls_id = self.tok.token_to_id("[CLS]")
        self.sep_id = self.tok.token_to_id("[SEP]")

    @property
    def name(self) -> str:
        return self.meta.get("name", "MuRIL (fine-tuned)")

    def _encode(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        ids = self.tok.encode(text, add_special_tokens=False).ids
        keep = self.max_len - 2
        if len(ids) > keep:  # keep the newest part of the conversation
            ids = ids[-keep:]
        ids = [self.cls_id] + ids + [self.sep_id]
        arr = np.array([ids], dtype=np.int64)
        return arr, np.ones_like(arr)

    def predict(self, text: str, history: list[tuple[str, str]] | None = None) -> StudentOutput:
        t0 = time.perf_counter()
        input_ids, mask = self._encode(compose(text, history))
        feed = {"input_ids": input_ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.zeros_like(input_ids)
        outs = dict(zip([o.name for o in self.sess.get_outputs()], self.sess.run(None, feed)))
        res: dict[str, dict[str, float]] = {}
        for head in HEADS:
            logits = np.asarray(outs[head])[0]
            if head in MULTI_LABEL:
                p = _sigmoid(logits)
            else:
                p = _softmax(logits, float(self.temperature.get(head, 1.0)))
            res[head] = {lab: float(v) for lab, v in zip(self.labels[head], p)}
        conf = max(res["care"].values())
        hi, lo = self.thresholds.get("band_high", 0.85), self.thresholds.get("band_low", 0.6)
        band = "high" if conf >= hi else "medium" if conf >= lo else "low"
        return StudentOutput(care=res["care"], urgency=res["urgency"], flags=res["flags"], tags=res["tags"],
                             who=res["who"], confidence=round(conf, 4), band=band,
                             latency_ms=round((time.perf_counter() - t0) * 1000, 2), thresholds=self.thresholds)


@lru_cache(maxsize=1)
def get_student() -> Student | None:
    if os.getenv("CC_STUDENT", "on").lower() in ("off", "0", "false"):
        return None
    if not (STUDENT_DIR / "model.onnx").exists():
        log.info("student model not found in %s; using rules + the old model", STUDENT_DIR)
        return None
    try:
        return Student(STUDENT_DIR)
    except Exception:  # never take the API down because of the model
        log.exception("could not load the student model; using rules + the old model")
        return None

"""Train the learned model on the doctor-labelled train set and pick the blend settings.

    python -m scripts.train_baseline data/provided/train.csv --text-col text --care-col care_type --urgency-col urgency

1. Cross-validates a TF-IDF (character + word n-grams over our normalised
   tokens) + logistic regression model for care type and urgency.
2. On the same folds, compares rules only, model only and blends, over a small
   grid of rules weight and under-triage cost, and picks the setting with the
   best proxy score that keeps every gold emergency caught.
3. Trains on all rows and writes models/baseline.joblib + baseline_meta.json,
   which the API loads on start (CC_MODEL=off disables it).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion

from app.config import MODELS_DIR, URGENCY_ORDER, internal_label, urgency_rank
from app.pipeline import run
from app.schemas import TriageRequest
from app.triage.model import blend_care, choose_urgency, features_text
from eval.metrics import macro_f1
from eval.run_eval import DEFAULT_LOCATION, _maybe_json, load_rows


def vectorizer() -> FeatureUnion:
    return FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), token_pattern=r"[^ ]+", sublinear_tf=True)),
    ])


def classifier() -> LogisticRegression:
    return LogisticRegression(max_iter=4000, class_weight="balanced", C=4.0)


def rules_decisions(rows: list[dict], texts: list[str], history_col: str) -> list[tuple[str, str]]:
    out = []
    for row, text in zip(rows, texts):
        history = _maybe_json(row.get(history_col) or [])
        req = TriageRequest(user_input=text, location=_maybe_json(row.get("location")) or DEFAULT_LOCATION,
                            conversation_history=history if isinstance(history, list) else [])
        resp = run(req, mode="batch", use_model=False)
        out.append((internal_label(resp.care_type), internal_label(resp.urgency)))
    return out


def score(gold_c, gold_u, pred_c, pred_u) -> dict:
    em_gold = [i for i, (c, u) in enumerate(zip(gold_c, gold_u)) if c == "emergency" or u == "immediate"]
    em_hit = [i for i in em_gold if pred_c[i] == "emergency" or pred_u[i] == "immediate"]
    under = sum(1 for g, p in zip(gold_u, pred_u) if urgency_rank(p) < urgency_rank(g)) / len(gold_u)
    recall = len(em_hit) / len(em_gold) if em_gold else 1.0
    f_c, f_u = macro_f1(gold_c, pred_c), macro_f1(gold_u, pred_u)
    proxy = 30 * (f_c + f_u) / 2 + 20 * max(0.0, recall - 0.5 * under)
    return {"care_f1": round(f_c, 3), "urgency_f1": round(f_u, 3), "emergency_recall": round(recall, 3),
            "under_triage": round(under, 3), "proxy": round(proxy, 2)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--care-col", default="care_type")
    ap.add_argument("--urgency-col", default="urgency")
    ap.add_argument("--history-col", default="conversation_history")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--out", type=Path, default=MODELS_DIR / "baseline.joblib")
    args = ap.parse_args(argv)

    rows = [r for r in load_rows(args.path)
            if r.get(args.text_col) and internal_label(r.get(args.care_col)) and internal_label(r.get(args.urgency_col))]
    texts = [str(r[args.text_col]) for r in rows]
    gold_c = [internal_label(r[args.care_col]) for r in rows]
    gold_u = [internal_label(r[args.urgency_col]) for r in rows]
    print(f"rows with labels: {len(rows)}")
    feats = [features_text(t) for t in texts]
    rules = rules_decisions(rows, texts, args.history_col)
    rules_c = [c or "gp" for c, _ in rules]
    rules_u = [u or "same_day" for _, u in rules]
    print("rules only      :", score(gold_c, gold_u, rules_c, rules_u))

    # out-of-fold model probabilities
    counts = {c: gold_c.count(c) for c in set(gold_c)}
    k = max(2, min(args.folds, min(counts.values())))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=7)
    oof_c: list[dict] = [dict() for _ in rows]
    oof_u: list[dict] = [dict() for _ in rows]
    for train_idx, test_idx in skf.split(feats, gold_c):
        vec = vectorizer()
        x_tr = vec.fit_transform([feats[i] for i in train_idx])
        x_te = vec.transform([feats[i] for i in test_idx])
        cc = classifier().fit(x_tr, [gold_c[i] for i in train_idx])
        cu = classifier().fit(x_tr, [gold_u[i] for i in train_idx])
        for row_i, pc, pu in zip(test_idx, cc.predict_proba(x_te), cu.predict_proba(x_te)):
            oof_c[row_i] = dict(zip(cc.classes_, map(float, pc)))
            oof_u[row_i] = dict(zip(cu.classes_, map(float, pu)))
    model_c = [max(p, key=p.get) for p in oof_c]
    model_u = [max(p, key=p.get) for p in oof_u]
    print(f"model only ({k}-fold):", score(gold_c, gold_u, model_c, model_u))

    # grid over blend settings, mirroring app.pipeline._apply_model
    best = None
    # no 0.0 weight (model alone) or 1.0 cost (no penalty for under-triage): the rules stay in charge
    for w in (0.2, 0.35, 0.5, 0.7, 1.0):  # 1.0 = rules decide, the model only adds emergencies
        for under_cost in (2.0, 3.0, 5.0):
            for thr in (0.2, 0.3, 0.4, 0.5):
                pc_all, pu_all = [], []
                for i in range(len(rows)):
                    if rules_c[i] == "emergency":
                        pc_all.append("emergency"), pu_all.append("immediate")
                        continue
                    if oof_c[i].get("emergency", 0) >= thr or oof_u[i].get("immediate", 0) >= thr:
                        pc_all.append("emergency"), pu_all.append("immediate")
                        continue
                    cb = blend_care({c: p for c, p in oof_c[i].items() if c != "emergency"}, rules_c[i], w)
                    ub = {u: (1 - w) * oof_u[i].get(u, 0) + w * (1.0 if u == rules_u[i] else 0.0) for u in URGENCY_ORDER}
                    u = choose_urgency(ub, under_cost)
                    if u == "immediate":
                        pc_all.append("emergency"), pu_all.append("immediate")
                    else:
                        pc_all.append(max(cb, key=cb.get)), pu_all.append(u)
                s = score(gold_c, gold_u, pc_all, pu_all)
                key = (s["emergency_recall"] >= 1.0, s["proxy"])
                if best is None or key > best[0]:
                    best = (key, {"rules_weight": w, "under_cost": under_cost, "emergency_threshold": thr}, s)
    print("best blend      :", best[2], "with", best[1])

    vec = vectorizer()
    x_all = vec.fit_transform(feats)
    bundle = {"vectorizer": vec, "care_clf": classifier().fit(x_all, gold_c),
              "urgency_clf": classifier().fit(x_all, gold_u)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.out)
    meta = {"trained_at": datetime.now().isoformat(timespec="seconds"), "source": str(args.path),
            "rows": len(rows), "folds": k, "settings": best[1], "cv": {"best_blend": best[2]},
            "labels": {"care": sorted(set(gold_c)), "urgency": sorted(set(gold_u))}}
    args.out.with_name(args.out.stem + "_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {args.out} (+ meta). Restart the API to load it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

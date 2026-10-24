"""Train the care-type model on the organisers' dataset with a split that cannot leak.

    python -m scripts.train_triage                       # data/sanocare_v1/triage_dataset.jsonl
    python -m scripts.train_triage --path other.jsonl

Why a grouped split. The 340 rows hold only 66 distinct messages, and those are 22
situations, each written in English, Hinglish and Hindi (Devanagari). A random split
would put the same message, or its translation, on both sides and report a score
the model has not earned. So every split here is by situation:

- test: 6 situations (one per class: paramedic, nurse, lab, gp, emergency, follow-up),
  chosen with a fixed seed and never used for any choice;
- validation: leave-one-situation-out over the other 16, used to pick the model's
  regularisation C and the rules weight in the blend;
- the chosen settings are scored once on test, then the deployed model is refit on
  all 22 situations (the test score above is the honest estimate).

Over- and under-fitting are checked by comparing training, validation and test
scores. Each distinct message counts once (duplicates differ only in location).
Writes models/triage.joblib and models/triage_meta.json (scores, split, settings).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

from app.config import MODELS_DIR, ORG_DATA_DIR, internal_care
from app.nlp.extract import extract
from app.triage.model import DEFAULTS, FOLLOWUP, features_text, fuse
from app.triage.rules import decide
from eval.metrics import macro_f1

SEED = 13
CLASSES = ["paramedic", "nurse", "lab", "gp", "emergency", FOLLOWUP]

# The 22 situations, each as English / Hinglish / Hindi (as written in the dataset).
SITUATIONS = {
    "fu_doctor": ["Doctor chahiye", "doctor chahiye", "डॉक्टर चाहिए"],
    "fu_hello": ["Hi, is anyone there?", "hello koi hai?", "नमस्ते, कोई है?"],
    "fu_help": ["I need help", "help chahiye", "मदद चाहिए"],
    "fu_book": ["I want to book something for my mother", "mummy ke liye kuch book karna hai", "माँ के लिए कुछ बुक करना है"],
    "em_collapse": ["He suddenly collapsed and is not responding", "wo achanak gir gaye response nahi de rahe",
                    "वो अचानक गिर गए और जवाब नहीं दे रहे"],
    "em_bleeding": ["Heavy bleeding that won't stop after an accident", "accident ke baad bleeding ruk nahi rahi",
                    "एक्सीडेंट के बाद खून नहीं रुक रहा"],
    "em_chest": ["My father is having severe chest pain and can't breathe", "papa ko severe chest pain hai saans nahi aa rahi",
                 "पापा को तेज सीने में दर्द है और सांस नहीं आ रही"],
    "nu_prescribed": ["Doctor prescribed an injection, can someone come home",
                      "doctor ne injection likha hai koi ghar aa sakta hai", "डॉक्टर ने इंजेक्शन लिखा है, घर कोई आ सकता है"],
    "nu_bedsore": ["Grandmother has a bedsore that needs dressing", "dadi ko bedsore dressing chahiye",
                   "दादी को घाव की ड्रेसिंग चाहिए"],
    "nu_insulin": ["Insulin injection help needed for elderly father", "papa ko insulin injection chahiye ghar pe",
                   "पापा को इंसुलिन लगवाना है"],
    "nu_im": ["Need an IM injection given at home", "ghar pe IM injection lagwana hai", "घर पर इंजेक्शन लगवाना है"],
    "nu_postop": ["Need wound dressing at home after surgery", "operation ke baad ghar pe dressing karani hai",
                  "ऑपरेशन के बाद घर पर ड्रेसिंग करवानी है"],
    "nu_wife": ["Post-operative dressing change required for my wife", "wife ki post-op dressing change karwani hai",
                "पत्नी की पट्टी बदलवानी है घर पर"],
    "lab_full": ["Book a full body checkup, home collection", "full body checkup home collection",
                 "फुल बॉडी चेकअप घर से सैंपल"],
    "lab_sugar": ["Need blood sugar test at home tomorrow morning", "kal subah sugar test ghar pe", "कल सुबह शुगर टेस्ट घर पर"],
    "lab_cbc": ["Want a CBC and thyroid test with home sample collection", "cbc aur thyroid test ghar se sample lekar",
                "सीबीसी और थायराइड टेस्ट घर से सैंपल लेकर"],
    "pm_weak": ["Grandfather is weak and not eating, want a home check-up", "dadaji weak hain, ghar pe checkup chahiye",
                "दादाजी कमजोर हैं, घर पर जांच चाहिए"],
    "pm_fever": ["My father has had fever and cough for 2 days", "papa ko do din se bukhar hai aur khansi bhi",
                 "पापा को दो दिन से बुखार और खांसी है"],
    "pm_bp": ["Need someone to check BP and sugar at home for my mother", "mummy ka bp sugar ghar pe check karwana hai",
              "माँ का बीपी और शुगर घर पर चेक करवाना है"],
    "gp_acidity": ["Mild acidity and gas since morning, want to consult a doctor",
                   "subah se acidity gas hai, doctor se consult karna hai", "सुबह से एसिडिटी है, डॉक्टर से सलाह चाहिए"],
    "gp_second": ["Need a second opinion on my child's prescription", "bacche ki medicine pe second opinion chahiye",
                  "बच्चे की दवा पर सेकंड ओपिनियन चाहिए"],
    "gp_reports": ["Want to talk to a doctor about my reports", "reports ke baare me doctor se baat karni hai",
                   "रिपोर्ट के बारे में डॉक्टर से बात करनी है"],
}
LANGS = ["English", "Hinglish", "Hindi"]


def vectorizer() -> FeatureUnion:
    return FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), token_pattern=r"[^ ]+", sublinear_tf=True)),
    ])


def fit(feats: list[str], labels: list[str], c: float) -> dict:
    vec = vectorizer()
    clf = LogisticRegression(max_iter=5000, class_weight="balanced", C=c).fit(vec.fit_transform(feats), labels)
    return {"vectorizer": vec, "care_clf": clf}


def probs(bundle: dict, feat: str) -> dict[str, float]:
    clf = bundle["care_clf"]
    return {k: float(v) for k, v in zip(clf.classes_, clf.predict_proba(bundle["vectorizer"].transform([feat]))[0])}


def final_care(p: dict[str, float], rules_care: str | None, rule_flags: bool, settings: dict) -> str:
    """Exactly what the API does: red-flag rules first, then a model emergency above
    its threshold, then the blend of model and rules (app.triage.model.fuse)."""
    if rule_flags or p.get("emergency", 0.0) >= settings["emergency_threshold"]:
        return "emergency"
    return fuse(p, rules_care, settings)[0]


def scores(gold: list[str], pred: list[str]) -> dict:
    em = [i for i, g in enumerate(gold) if g == "emergency"]
    non = [i for i, g in enumerate(gold) if g != "emergency"]
    return {"accuracy": round(sum(g == p for g, p in zip(gold, pred)) / len(gold), 3),
            "macro_f1": round(macro_f1(gold, pred), 3),
            "emergency_recall": round(sum(pred[i] == "emergency" for i in em) / len(em), 3) if em else None,
            "false_emergency": round(sum(pred[i] == "emergency" for i in non) / len(non), 3) if non else None,
            "n": len(gold)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", type=Path, default=ORG_DATA_DIR / "triage_dataset.jsonl")
    ap.add_argument("--out", type=Path, default=MODELS_DIR / "triage.joblib")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    rows = [json.loads(line) for line in args.path.read_text(encoding="utf-8").splitlines() if line.strip()]
    label: dict[str, str] = {}
    lang: dict[str, str] = {}
    for r in rows:
        t = r["request"]["user_input"]
        g = internal_care(r["response"]["care_type"]) or FOLLOWUP
        if label.setdefault(t, g) != g:
            raise SystemExit(f"conflicting labels for {t!r}")
        lang[t] = r.get("detected_language", "")
    situation = {t: s for s, ts in SITUATIONS.items() for t in ts}
    missing = [t for t in label if t not in situation]
    if missing:
        raise SystemExit(f"messages without a situation: {missing}")
    print(f"rows {len(rows)}, distinct messages {len(label)}, situations {len(SITUATIONS)}")

    # features and the rules' own answer, once per message
    feat, rules_care, flags = {}, {}, {}
    for t in label:
        ex = extract(t)
        feat[t] = features_text(t, ex)
        flags[t] = bool(ex.red_flags)
        rules_care[t] = None if ex.red_flags else decide(ex).care

    # fixed test situations: one per class, seeded
    rng = random.Random(SEED)
    by_class = defaultdict(list)
    for s, ts in SITUATIONS.items():
        by_class[label[ts[0]]].append(s)
    test_sit = sorted(rng.choice(sorted(v)) for k, v in sorted(by_class.items()))
    train_sit = [s for s in SITUATIONS if s not in test_sit]
    print("test situations:", test_sit)

    def texts(sits):
        return [t for s in sits for t in SITUATIONS[s]]

    # leave-one-situation-out validation on the 16 training situations
    grid_c = [0.5, 1.0, 2.0, 4.0, 8.0]
    grid_w = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6]
    oof = {c: {} for c in grid_c}
    for c in grid_c:
        for held in train_sit:
            tr = texts([s for s in train_sit if s != held])
            bundle = fit([feat[t] for t in tr], [label[t] for t in tr], c)
            for t in SITUATIONS[held]:
                oof[c][t] = probs(bundle, feat[t])
    val_texts = texts(train_sit)
    gold_val = [label[t] for t in val_texts]
    results = []
    for c in grid_c:
        for w in grid_w:
            s = dict(DEFAULTS, rules_weight=w)
            pred = [final_care(oof[c][t], rules_care[t], flags[t], s) for t in val_texts]
            model_only = [max((k for k in oof[c][t]), key=oof[c][t].get) for t in val_texts]
            sc = scores(gold_val, pred)
            # ties go to a rules weight near 0.4: the model then overrides the rules only when
            # it is clearly sure (messages unlike the training data give it flat probabilities)
            results.append(((sc["emergency_recall"] or 0) >= 1.0, sc["macro_f1"], -abs(w - 0.4), c, w, sc,
                             scores(gold_val, model_only)))
    results.sort(key=lambda r: r[:3], reverse=True)
    _, _, _, best_c, best_w, val_score, val_model_only = results[0]
    settings = dict(DEFAULTS, rules_weight=best_w)
    print(f"validation (leave-one-situation-out, {len(val_texts)} messages): C={best_c} rules_weight={best_w}")
    print("  model + rules:", val_score)
    print("  model alone  :", val_model_only)
    print("  rules alone  :", scores(gold_val, ["emergency" if flags[t] else (rules_care[t] or FOLLOWUP)
                                                 for t in val_texts]))

    # one look at test with the chosen settings, model fit on the 16 training situations
    bundle = fit([feat[t] for t in val_texts], gold_val, best_c)
    train_pred = [final_care(probs(bundle, feat[t]), rules_care[t], flags[t], settings) for t in val_texts]
    test_texts = texts(test_sit)
    gold_test = [label[t] for t in test_texts]
    test_p = {t: probs(bundle, feat[t]) for t in test_texts}
    test_pred = [final_care(test_p[t], rules_care[t], flags[t], settings) for t in test_texts]
    test_model_only = [max(test_p[t], key=test_p[t].get) for t in test_texts]
    train_score, test_score = scores(gold_val, train_pred), scores(gold_test, test_pred)
    print(f"train fit ({len(val_texts)}):", train_score)
    print(f"test ({len(test_texts)} messages, unseen situations): model + rules:", test_score)
    print("                                          model alone  :", scores(gold_test, test_model_only))
    by_lang = {lg: scores([label[t] for t in test_texts if lang[t] == lg],
                          [p for t, p in zip(test_texts, test_pred) if lang[t] == lg]) for lg in LANGS}
    print("test by language:", {k: v["accuracy"] for k, v in by_lang.items()})
    for t, g, p in zip(test_texts, gold_test, test_pred):
        if g != p:
            print(f"  test miss: {t!r} gold={g} pred={p}")

    # deploy: refit on all 22 situations with the chosen settings
    all_texts = list(label)
    final = fit([feat[t] for t in all_texts], [label[t] for t in all_texts], best_c)
    lat = []
    for t in all_texts * 5:
        t0 = time.perf_counter()
        probs(final, features_text(t))
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    latency = {"p50_ms": round(statistics.median(lat), 2), "p95_ms": round(lat[int(0.95 * len(lat))], 2)}
    print("model latency (features + predict):", latency)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, args.out)
    meta = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(args.path.as_posix()), "rows": len(rows), "distinct_messages": len(label),
        "situations": len(SITUATIONS), "classes": sorted(set(label.values())),
        "split": {"method": "by situation (all three languages together)", "seed": SEED,
                  "test_situations": test_sit, "validation": "leave-one-situation-out on the other 16"},
        "settings": settings, "C": best_c,
        "scores": {"train_fit": train_score, "validation": val_score, "validation_model_alone": val_model_only,
                   "test": test_score, "test_model_alone": scores(gold_test, test_model_only),
                   "test_by_language": by_lang},
        "latency": latency,
        "note": "test = situations never seen in training or tuning; the deployed model is refit on all 22.",
    }
    args.out.with_name(args.out.stem + "_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {args.out} and {args.out.stem}_meta.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

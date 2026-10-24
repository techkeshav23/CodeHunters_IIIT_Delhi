"""Compare the triage systems on the same test sets (the table in docs/RESULTS.md).

Systems (each run in its own process so model caches and env switches cannot leak):
  rules          lexicon + rules only                         CC_STUDENT=off CC_MODEL=off
  rules+tfidf    the previous system (rules + TF-IDF/LR)        CC_STUDENT=off
  muril          the fine-tuned MuRIL with guardrails          (default)
  muril+claude   as above, Claude Opus 5.5 when MuRIL is unsure CC_LLM_FALLBACK=on

Test sets (none of them is used in training):
  organisers     the organisers' 340 labelled rows
  redteam        our hand-written hard cases (eval/cases/redteam_*.jsonl)
  carebench      CARE-Bench public prefixes (safety only; cited in the write-up)

    python -m scripts.compare_models                  # all systems -> docs/RESULTS_MODELS.md
    python -m scripts.compare_models --one muril      # one system, JSON to stdout
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = {
    "rules": {"CC_STUDENT": "off", "CC_MODEL": "off", "CC_LLM_FALLBACK": "off"},
    "rules+tfidf": {"CC_STUDENT": "off", "CC_LLM_FALLBACK": "off"},
    "muril": {"CC_LLM_FALLBACK": "off"},
    "muril+claude": {"CC_LLM_FALLBACK": "on"},
}
NAMES = {"rules": "Rules only", "rules+tfidf": "Rules + TF-IDF/LR (previous)", "muril": "MuRIL + guardrails (new)",
         "muril+claude": "MuRIL + guardrails + Claude when unsure"}


def run_one() -> dict:
    import time

    import numpy as np
    from sklearn.metrics import f1_score

    from eval.run_eval import evaluate, load_rows

    out: dict = {}
    org = load_rows(ROOT / "data" / "sanocare_v1" / "triage_dataset.jsonl")
    r = evaluate(org, mode="interactive")["results"]  # as the API answers the organisers' scorer
    gc = [x["gold_care"] or "followup" for x in r]
    pc = [x["pred_care"] if x["pred_care"] != "none" else "followup" for x in r]
    gu = [x["gold_urgency"] or "followup" for x in r]
    pu = [x["pred_urgency"] if x["pred_urgency"] != "none" else "followup" for x in r]
    em = np.array([x["expect_emergency"] for x in r], dtype=bool)
    pe = np.array([x["pred_emergency"] for x in r], dtype=bool)
    out["organisers"] = {
        "n": len(r),
        "care_macro_f1": round(float(f1_score(gc, pc, average="macro")), 4),
        "urgency_macro_f1": round(float(f1_score(gu, pu, average="macro")), 4),
        "care_accuracy": round(float(np.mean(np.array(gc) == np.array(pc))), 4),
        "emergency_recall": round(float(pe[em].mean()), 4),
        "false_emergency": round(float(pe[~em].mean()), 4),
        "latency_ms_p50": round(float(np.median([x["timing_ms"] for x in r])), 2),
        "misses": [(x["text"], x["gold_care"], x["pred_care"]) for x in r if (x["gold_care"] or "followup") !=
                   (x["pred_care"] if x["pred_care"] != "none" else "followup")][:20],
    }
    rt_rows = []
    for p in sorted((ROOT / "eval" / "cases").glob("redteam_*.jsonl")):
        rt_rows += load_rows(p)
    rr = evaluate(rt_rows, mode="batch")["results"]
    hard = [x for x in rr if x["difficulty"] != "hard"]
    em = np.array([x["expect_emergency"] is True for x in hard])
    neg = np.array([x["expect_emergency"] is False for x in hard])
    pe = np.array([x["pred_emergency"] for x in hard])
    labelled = [x for x in hard if x["gold_care"]]
    out["redteam"] = {
        "n": len(hard),
        "emergency_recall": round(float(pe[em].mean()), 4) if em.any() else None,
        "false_emergency": round(float(pe[neg].mean()), 4) if neg.any() else None,
        "care_accuracy_labelled": round(float(np.mean([x["gold_care"] == x["pred_care"] for x in labelled])), 4)
        if labelled else None,
        "n_labelled": len(labelled),
        "missed_emergencies": [x["text"] for x, e, p in zip(hard, em, pe) if e and not p][:20],
        "false_alarms": [x["text"] for x, n_, p in zip(hard, neg, pe) if n_ and p][:20],
    }
    try:
        from scripts.external_carebench import predict, safety_rates

        cb = ROOT / "data" / "external" / "care_bench"
        out["carebench"] = safety_rates(predict(cb / "evaluation_prefixes_public.jsonl", ask=False))
    except Exception as e:  # the external set is optional
        out["carebench"] = {"error": f"{type(e).__name__}: {e}"}
    out["finished"] = time.strftime("%H:%M:%S")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", choices=list(SYSTEMS))
    ap.add_argument("--systems", default=",".join(SYSTEMS))
    args = ap.parse_args()
    if args.one:
        print(json.dumps(run_one(), ensure_ascii=False))
        return 0
    results = {}
    for name in args.systems.split(","):
        env = {**os.environ, **SYSTEMS[name], "PYTHONIOENCODING": "utf-8"}
        p = subprocess.run([sys.executable, "-m", "scripts.compare_models", "--one", name], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8")
        if p.returncode != 0:
            print(name, "failed:", p.stderr[-2000:])
            continue
        results[name] = json.loads(p.stdout.strip().splitlines()[-1])
        o, rt = results[name]["organisers"], results[name]["redteam"]
        print(f"{name:14s} org care F1 {o['care_macro_f1']:.3f} urg F1 {o['urgency_macro_f1']:.3f} "
              f"em recall {o['emergency_recall']:.3f} false em {o['false_emergency']:.3f} | redteam recall "
              f"{rt['emergency_recall']} false {rt['false_emergency']} care {rt['care_accuracy_labelled']} "
              f"| {o['latency_ms_p50']} ms")
    (ROOT / "eval" / "out").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval" / "out" / "compare_models.json").write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                                                encoding="utf-8")
    lines = ["# Model comparison", "", "Same test sets for every system; none of them is used in training.", "",
             "| System | Organisers 340: care F1 | urgency F1 | emergency recall | false emergency | "
             "Hard cases: emergency recall | false alarms | care acc | CARE-Bench urgent>=same_day | p50 ms |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        o, rt, cb = r["organisers"], r["redteam"], r.get("carebench", {})
        cbv = round(cb["urgent_recall"], 3) if isinstance(cb, dict) and "urgent_recall" in cb else None
        lines.append(f"| {NAMES[name]} | {o['care_macro_f1']:.3f} | {o['urgency_macro_f1']:.3f} | "
                     f"{o['emergency_recall']:.3f} | {o['false_emergency']:.3f} | {rt['emergency_recall']} | "
                     f"{rt['false_emergency']} | {rt['care_accuracy_labelled']} | {cbv} | {o['latency_ms_p50']} |")
    (ROOT / "docs" / "RESULTS_MODELS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

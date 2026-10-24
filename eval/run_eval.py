"""Run the pipeline over a labelled file and report the problem statement's metrics.

    python -m eval.run_eval eval/cases/redteam_v0.jsonl
    python -m eval.run_eval data/provided/train.csv --text-col text --care-col care_type --urgency-col urgency

Rows may be JSONL or CSV. Labels can be API values (paramedic_home_visit) or
internal keys (paramedic). The proxy score is our own estimate, not the
organisers' formula: 30 x routing macro-F1 + 20 x safety (+ 20 x NDCG@3 when
matching labels exist).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from app.config import internal_label, urgency_rank
from app.pipeline import run
from app.schemas import TriageRequest
from eval.metrics import confusion, macro_f1, ndcg_at_k, per_class, percentile

DEFAULT_LOCATION = {"lat": 28.5459, "lng": 77.2732}  # IIIT-Delhi


def load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    if len(rows) == 1 and isinstance(rows[0], list):
        rows = rows[0]
    return rows


def _maybe_json(value):
    if isinstance(value, str) and value.strip()[:1] in "[{":
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _bool(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def evaluate(rows: list[dict], text_col: str = "text", id_col: str = "id", care_col: str = "care",
             urgency_col: str = "urgency", history_col: str = "history", mode: str = "batch",
             policy: str | None = None, matches_col: str = "best_caregivers") -> dict:
    results = []
    for i, row in enumerate(rows):
        text = row.get(text_col) or row.get("user_input") or ""
        history = _maybe_json(row.get(history_col) or row.get("conversation_history") or [])
        loc = _maybe_json(row.get("location")) or DEFAULT_LOCATION
        if row.get("lat") not in (None, "") and row.get("lng") not in (None, ""):
            loc = {"lat": float(row["lat"]), "lng": float(row["lng"])}
        req = TriageRequest(user_input=text, language=row.get("language") or "auto", location=loc,
                            conversation_history=history if isinstance(history, list) else [])
        t0 = time.perf_counter()
        resp = run(req, mode=mode, policy=policy, explain=True)
        wall_ms = (time.perf_counter() - t0) * 1000
        pred_care = internal_label(resp.care_type) or ("followup" if resp.follow_up_question else "none")
        pred_urg = internal_label(resp.urgency) or ("followup" if resp.follow_up_question else "none")
        gold_care = internal_label(row.get(care_col) or row.get("care_type"))
        gold_urg = internal_label(row.get(urgency_col))
        expect_em = _bool(row.get("expect_emergency"))
        if expect_em is None and (gold_care or gold_urg):
            expect_em = gold_care == "emergency" or gold_urg == "immediate"
        pred_em = pred_care == "emergency" or pred_urg == "immediate"
        flags_any = _maybe_json(row.get("flags_any")) or []
        gold_matches = _maybe_json(row.get(matches_col)) or []
        results.append({
            "id": row.get(id_col) or f"row_{i + 1}", "text": text, "category": row.get("category"),
            "difficulty": row.get("difficulty") or "normal",
            "gold_care": gold_care, "gold_urgency": gold_urg, "expect_emergency": expect_em,
            "pred_care": pred_care, "pred_urgency": pred_urg, "pred_emergency": pred_em,
            "red_flags": resp.red_flags, "flags_any": flags_any,
            "follow_up": resp.follow_up_question, "follow_up_id": (resp.trace.get("follow_up") or {}).get("id"),
            "expect_followup": row.get("expect_followup"),
            "matched": [m.caregiver_id for m in resp.matched_caregivers], "gold_matches": gold_matches,
            "reasoning": resp.reasoning, "rule": resp.trace.get("decision", {}).get("rule"),
            "timing_ms": resp.trace.get("timing_ms"), "wall_ms": round(wall_ms, 2),
        })
    return {"results": results, "metrics": summarise(results)}


def summarise(results: list[dict]) -> dict:
    m: dict = {"n": len(results)}
    care_rows = [r for r in results if r["gold_care"]]
    urg_rows = [r for r in results if r["gold_urgency"]]
    if care_rows:
        m["care_macro_f1"] = macro_f1([r["gold_care"] for r in care_rows], [r["pred_care"] for r in care_rows])
        m["care_per_class"] = per_class([r["gold_care"] for r in care_rows], [r["pred_care"] for r in care_rows])
        m["care_confusion"] = {g: dict(c) for g, c in confusion([r["gold_care"] for r in care_rows],
                                                                [r["pred_care"] for r in care_rows]).items()}
    if urg_rows:
        m["urgency_macro_f1"] = macro_f1([r["gold_urgency"] for r in urg_rows], [r["pred_urgency"] for r in urg_rows])
        under = [r for r in urg_rows if urgency_rank(r["pred_urgency"]) < urgency_rank(r["gold_urgency"])]
        m["under_triage_rate"] = len(under) / len(urg_rows)
        m["under_triage_ids"] = [r["id"] for r in under]
    em_rows = [r for r in results if r["expect_emergency"] is True and r["difficulty"] != "hard"]
    non_rows = [r for r in results if r["expect_emergency"] is False and r["difficulty"] != "hard"]
    if em_rows:
        hits = [r for r in em_rows if r["pred_emergency"]]
        m["emergency_recall"] = len(hits) / len(em_rows)
        m["emergency_missed_ids"] = [r["id"] for r in em_rows if not r["pred_emergency"]]
        flagged = [r for r in em_rows if r["flags_any"]]
        if flagged:
            m["flag_match_rate"] = sum(1 for r in flagged if set(r["flags_any"]) & set(r["red_flags"])) / len(flagged)
    if non_rows:
        fa = [r for r in non_rows if r["pred_emergency"]]
        m["false_alarm_rate"] = len(fa) / len(non_rows)
        m["false_alarm_ids"] = [r["id"] for r in fa]
    fu_rows = [r for r in results if r.get("expect_followup")]
    if fu_rows:
        m["followup_match_rate"] = sum(1 for r in fu_rows if r["follow_up_id"] == r["expect_followup"]) / len(fu_rows)
    m["followups_asked"] = sum(1 for r in results if r["follow_up"])
    match_rows = [r for r in results if r["gold_matches"]]
    if match_rows:
        m["ndcg_at_3"] = sum(ndcg_at_k(r["matched"], r["gold_matches"], 3) for r in match_rows) / len(match_rows)
    lat = [r["timing_ms"] for r in results if r["timing_ms"] is not None]
    m["latency_ms_p50"] = round(percentile(lat, 0.5), 2)
    m["latency_ms_p95"] = round(percentile(lat, 0.95), 2)

    routing = [v for v in (m.get("care_macro_f1"), m.get("urgency_macro_f1")) if v is not None]
    if routing or "emergency_recall" in m:
        r_score = sum(routing) / len(routing) if routing else 0.0
        safety = max(0.0, m.get("emergency_recall", 1.0) - 0.5 * m.get("under_triage_rate", 0.0))
        proxy = 30 * r_score + 20 * safety
        out_of = 50
        if "ndcg_at_3" in m:
            proxy += 20 * m["ndcg_at_3"]
            out_of = 70
        m["proxy_score"] = round(proxy, 1)
        m["proxy_out_of"] = out_of
    return m


def report(m: dict, results: list[dict]) -> str:
    lines = [f"cases: {m['n']}"]
    for key in ("care_macro_f1", "urgency_macro_f1", "emergency_recall", "false_alarm_rate", "under_triage_rate",
                "flag_match_rate", "followup_match_rate", "ndcg_at_3"):
        if key in m:
            lines.append(f"{key:>22}: {m[key]:.3f}")
    lines.append(f"{'followups_asked':>22}: {m['followups_asked']}")
    lines.append(f"{'latency_ms p50/p95':>22}: {m['latency_ms_p50']} / {m['latency_ms_p95']}")
    if "proxy_score" in m:
        lines.append(f"{'proxy score':>22}: {m['proxy_score']} / {m['proxy_out_of']}  (our estimate, auto-scored part)")
    if "care_per_class" in m:
        lines.append("care per class (P / R / F1 / n):")
        for lab, v in m["care_per_class"].items():
            lines.append(f"   {lab:>12}: {v['precision']:.2f} / {v['recall']:.2f} / {v['f1']:.2f} / {v['support']}")
    by_id = {r["id"]: r for r in results}
    for title, key in (("MISSED EMERGENCIES", "emergency_missed_ids"), ("FALSE ALARMS", "false_alarm_ids"),
                       ("UNDER-TRIAGE", "under_triage_ids")):
        ids = m.get(key) or []
        if ids:
            lines.append(f"{title} ({len(ids)}):")
            for i in ids:
                r = by_id[i]
                lines.append(f"   {i}: {r['text']!r} -> {r['pred_care']}/{r['pred_urgency']} flags={r['red_flags']}")
    wrong = [r for r in results if r["gold_care"] and r["gold_care"] != r["pred_care"] and not r["pred_emergency"]]
    if wrong:
        lines.append(f"CARE MISMATCHES ({len(wrong)}):")
        for r in wrong:
            lines.append(f"   {r['id']}: {r['text']!r} gold={r['gold_care']}/{r['gold_urgency']} "
                         f"pred={r['pred_care']}/{r['pred_urgency']} rule={r['rule']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--id-col", default="id")
    ap.add_argument("--care-col", default="care")
    ap.add_argument("--urgency-col", default="urgency")
    ap.add_argument("--history-col", default="history")
    ap.add_argument("--matches-col", default="best_caregivers")
    ap.add_argument("--mode", choices=["batch", "interactive"], default="batch")
    ap.add_argument("--policy", choices=["minimal", "safety"], default=None)
    ap.add_argument("--out", type=Path, default=Path("eval/out"))
    ap.add_argument("--fail-on-miss", action="store_true", help="exit 1 if any emergency is missed")
    args = ap.parse_args(argv)

    rows = load_rows(args.path)
    res = evaluate(rows, args.text_col, args.id_col, args.care_col, args.urgency_col, args.history_col,
                   args.mode, args.policy, args.matches_col)
    print(report(res["metrics"], res["results"]))
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.path.stem
    (args.out / f"{stem}_predictions.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in res["results"]) + "\n", encoding="utf-8")
    (args.out / f"{stem}_metrics.json").write_text(json.dumps(res["metrics"], indent=1, default=str), encoding="utf-8")
    print(f"\nwrote {args.out / (stem + '_predictions.jsonl')}")
    if args.fail_on_miss and res["metrics"].get("emergency_missed_ids"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

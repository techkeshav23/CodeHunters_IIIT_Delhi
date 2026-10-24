"""Caregiver matching against the organisers' reference labels.

    python -m scripts.eval_matching
    python -m scripts.eval_matching data/sanocare_v1/triage_dataset.jsonl --caregivers data/sanocare_v1/caregivers.csv
    python -m scripts.eval_matching --show 20          # print up to 20 rows that differ
    python -m scripts.eval_matching --end-to-end       # predicted care type (full pipeline), not the gold one
    python -m scripts.eval_matching --now 2026-10-24T17:00:00+05:30 --ties available

For every labelled row with a care type, we rank the roster with the gold care type (our
NLP still reads the text: language and the service asked for) and compare with
response.matched_caregivers. Emergencies and follow-ups have no caregivers on either side.

The labels keep a random 1-3 of the reference ranking, so "list match" compares our list cut
to the label's length; "strict list match" compares our whole top-3 (it can only agree when
the label happened to keep all of them).

The clock is fixed (--now, default 2026-10-24 11:00 IST) so runs are repeatable: it sets the
availability words in our reasons ("free now till 9 pm", where the labels write the window,
"free 15:00–21:00", so reasons are compared without that part) and, with --ties, how equal
scores are ordered. "list_match_by_ties" shows what each tie-break would do to the list match
at that clock (the labels keep roster order on ties, so only "roster" reproduces them at
every hour).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from app import config
from app.config import internal_care, internal_urgency
from app.matching import ranker
from app.matching.caregivers import ORG_ROSTER, _load_rows, load, now
from app.matching.ranker import TIE_MODES, rank
from app.nlp.extract import extract
from eval.metrics import ndcg_at_k

DEFAULT_DATA = config.ORG_DATA_DIR / "triage_dataset.jsonl"
DEFAULT_NOW = "2026-10-24T11:00:00+05:30"


def load_rows(path: Path) -> list[dict]:
    """Rows as written: the nested jsonl (id, request, response) or the flat csv."""
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _gold(row: dict) -> tuple[dict, dict]:
    """(request, response) from the nested jsonl shape or a flat row."""
    if "request" in row:
        return row["request"], row.get("response") or {}
    req = {"user_input": row.get("user_input") or row.get("text", ""),
           "location": {"lat": float(row["lat"]), "lng": float(row["lng"])} if row.get("lat") else None}
    ids = [i for i in str(row.get("matched_caregiver_ids") or "").replace(";", "|").split("|") if i]
    return req, {"care_type": row.get("care_type") or None, "urgency": row.get("urgency") or None,
                 "matched_caregivers": [{"caregiver_id": i, "score": None, "reason": None} for i in ids]}


def predict(req: dict, resp: dict, pool, end_to_end: bool, ref: datetime | None = None,
            ties: str | None = None) -> tuple[list[dict], str | None]:
    """Our matched caregivers [{caregiver_id, score, reason}] and the care type used. The
    pipeline (end to end) reads its clock from CC_NOW / config.NOW_OVERRIDE and its tie-break
    from ranker.TIES; main() sets both."""
    if end_to_end:
        from app.pipeline import run
        from app.schemas import TriageRequest
        out = run(TriageRequest(user_input=req.get("user_input", ""), language=req.get("language", "auto"),
                                location=req.get("location"), conversation_history=[]), mode="interactive")
        return [m.model_dump() for m in out.matched_caregivers], out.care_type
    care = internal_care(resp.get("care_type"))
    if care is None:
        return [], None
    loc = req.get("location") or None
    ex = extract(req.get("user_input", ""), req.get("language", "auto"))
    matches = rank(care, internal_urgency(resp.get("urgency")) or "same_day", ex,
                   (loc["lat"], loc["lng"]) if loc else None, caregivers=pool, ref=ref or now(), ties=ties)
    return [{"caregiver_id": m.caregiver.id, "score": m.score, "reason": m.reason} for m in matches], \
        resp.get("care_type")


def _strip_language(reason: str | None) -> str:
    """The reason without its "X-speaking" part (the labels name the request's language even
    when the caregiver does not list it; we name the language they actually share)."""
    parts = (reason or "").split(", ")
    return ", ".join(parts[1:] if parts and parts[0].endswith("-speaking") else parts)


def _strip_time(reason: str | None) -> str:
    """The reason without its availability part ("free 15:00–21:00" in the labels, "free now
    till 9 pm" or "free from 4 pm" in ours, depending on the clock)."""
    return ", ".join(p for p in (reason or "").split(", ") if not p.startswith(("free ", "no free slot")))


def evaluate(rows: list[dict], pool, end_to_end: bool = False, show: int = 10, ref: datetime | None = None,
             ties: str | None = None) -> dict:
    n = Counter()
    by_care = defaultdict(Counter)
    p_at_k, recall3, ndcg, abs_err = [], [], [], []
    shown = 0
    extra_rows, missing_rows = [], []
    for row in rows:
        req, resp = _gold(row)
        gold = resp.get("matched_caregivers") or []
        care = resp.get("care_type")
        if not care or care == config.CARE_TYPES["emergency"]:
            if not end_to_end:
                continue  # follow-ups and emergencies: no caregivers by construction
        ours, used_care = predict(req, resp, pool, end_to_end, ref, ties)
        rid = row.get("id", "?")
        gids = [g["caregiver_id"] for g in gold]
        oids = [o["caregiver_id"] for o in ours]
        n["rows"] += 1
        bc = by_care[care or "null"]
        bc["rows"] += 1
        if not gold:
            n["gold_empty"] += 1
            if ours:
                n["ours_not_gold"] += 1
                extra_rows.append((rid, care, oids))
            else:
                n["both_empty"] += 1
                bc["list_match"] += 1
            continue
        n["gold_nonempty"] += 1
        if not ours:
            n["gold_not_ours"] += 1
            missing_rows.append((rid, care, gids))
        k = len(gold)
        prefix_ok = oids[:k] == gids
        n["list_match"] += prefix_ok
        bc["list_match"] += prefix_ok
        n["strict_list_match"] += oids == gids
        n["top1_match"] += bool(oids) and oids[0] == gids[0]
        gscores = [g.get("score") for g in gold]
        if prefix_ok and all(s is not None for s in gscores):
            ok = [o["score"] for o in ours[:k]] == gscores
            n["list_and_scores_match"] += ok
        p_at_k.append(len(set(oids[:k]) & set(gids)) / k)
        recall3.append(len(set(oids[:3]) & set(gids)) / k)
        ndcg.append(ndcg_at_k(oids, gids, 3))
        mine = {o["caregiver_id"]: o for o in ours}
        for g in gold:
            o = mine.get(g["caregiver_id"])
            if o is None or g.get("score") is None:
                continue
            abs_err.append(abs(o["score"] - g["score"]))
            if g.get("reason"):
                n["reasons_compared"] += 1
                n["reason_exact_but_time"] += _strip_time(o["reason"]) == _strip_time(g["reason"])
                n["reason_same_but_lang_time"] += (_strip_time(_strip_language(o["reason"]))
                                                   == _strip_time(_strip_language(g["reason"])))
        if not prefix_ok and shown < show:
            shown += 1
            print(f"  differs {rid} [{care} -> {used_care}] {req.get('user_input', '')[:60]!r}")
            print(f"     gold {[(g['caregiver_id'], g.get('score')) for g in gold]}")
            print(f"     ours {[(o['caregiver_id'], o['score']) for o in ours]}")

    def rate(a, b):
        return round(n[a] / n[b], 4) if n[b] else None

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "rows_compared": n["rows"],
        "label_has_caregivers": n["gold_nonempty"],
        "label_empty": n["gold_empty"],
        "list_match": rate("list_match", "gold_nonempty"),
        "list_match_rows": f"{n['list_match']}/{n['gold_nonempty']}",
        "list_and_scores_match": rate("list_and_scores_match", "gold_nonempty"),
        "strict_list_match": rate("strict_list_match", "gold_nonempty"),
        "top1_match": rate("top1_match", "gold_nonempty"),
        "precision_at_k": mean(p_at_k),
        "set_overlap_recall_at_3": mean(recall3),
        "ndcg_at_3": mean(ndcg),
        "score_mae": mean(abs_err),
        "empty_agreement": rate("both_empty", "gold_empty"),
        "ours_but_label_empty": n["ours_not_gold"],
        "label_but_ours_empty": n["gold_not_ours"],
        "reason_exact_except_time": rate("reason_exact_but_time", "reasons_compared"),
        "reason_same_except_lang_time": rate("reason_same_but_lang_time", "reasons_compared"),
        "list_match_by_care_type": {c: f"{v['list_match']}/{v['rows']}" for c, v in sorted(by_care.items())},
        "ours_but_label_empty_rows": extra_rows[:20],
        "label_but_ours_empty_rows": missing_rows[:20],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path, nargs="?", default=DEFAULT_DATA)
    ap.add_argument("--caregivers", type=Path, default=ORG_ROSTER,
                    help="roster the labels were made with (default: data/sanocare_v1/caregivers.csv)")
    ap.add_argument("--end-to-end", action="store_true", help="use the pipeline's care type instead of the gold one")
    ap.add_argument("--show", type=int, default=10, help="rows that differ to print")
    ap.add_argument("--min-list-match", type=float, default=None, help="exit 1 below this list match rate")
    ap.add_argument("--json", action="store_true", help="print the metrics as JSON only")
    ap.add_argument("--now", default=DEFAULT_NOW,
                    help=f"the clock, ISO with offset (default {DEFAULT_NOW}); 'live' for the real time")
    ap.add_argument("--ties", choices=TIE_MODES, default=None,
                    help=f"how equal scores are ordered (default: the service's, now {ranker.TIES!r})")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.now != "live":
        config.NOW_OVERRIDE = args.now  # the pipeline and now() read it
    if args.ties:
        ranker.TIES = args.ties
    ref = now()
    rows = load_rows(args.path)
    if args.end_to_end:  # the pipeline matches against the service's own pool
        pool, source = load()
        source = f"the service's pool ({source}), end to end"
    else:
        pool, source = _load_rows(args.caregivers), f"{args.caregivers}, gold care type"
    if not args.json:
        print(f"{len(rows)} labelled rows from {args.path}; {len(pool)} caregivers from {source}; "
              f"clock {ref:%Y-%m-%d %H:%M %Z}, ties {ranker.TIES!r}")
    metrics = evaluate(rows, pool, end_to_end=args.end_to_end, show=0 if args.json else args.show, ref=ref)
    if not args.end_to_end:
        by_ties = {}
        for mode in TIE_MODES:
            m = metrics if mode == ranker.TIES else evaluate(rows, pool, show=0, ref=ref, ties=mode)
            by_ties[mode] = m["list_match_rows"]
        metrics["list_match_by_ties"] = by_ties
    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        for k, v in metrics.items():
            print(f"{k:32s} {v}")
    if args.min_list_match is not None and (metrics["list_match"] or 0) < args.min_list_match:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

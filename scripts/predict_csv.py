"""Predictions file for the hidden test set (deliverable 3).

    python -m scripts.predict_csv data/provided/test.csv --out predictions.csv

Runs the same pipeline as the API in batch mode (never asks a follow-up
question, always returns a decision). Column names are flags until the
organisers publish the CSV format.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from app.pipeline import run
from app.schemas import TriageRequest
from eval.run_eval import DEFAULT_LOCATION, _maybe_json, load_rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--out", type=Path, default=Path("predictions.csv"))
    ap.add_argument("--id-col", default="id")
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--history-col", default="conversation_history")
    ap.add_argument("--sep", default="|", help="separator inside list columns")
    args = ap.parse_args(argv)

    rows = load_rows(args.path)
    fields = ["id", "care_type", "urgency", "red_flags", "matched_caregivers", "scores", "reasoning"]
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for i, row in enumerate(rows):
            loc = _maybe_json(row.get("location")) or DEFAULT_LOCATION
            if row.get("lat") not in (None, "") and row.get("lng") not in (None, ""):
                loc = {"lat": float(row["lat"]), "lng": float(row["lng"])}
            history = _maybe_json(row.get(args.history_col) or [])
            req = TriageRequest(user_input=row.get(args.text_col) or row.get("user_input") or "",
                                language=row.get("language") or "auto", location=loc,
                                conversation_history=history if isinstance(history, list) else [])
            resp = run(req, mode="batch")
            w.writerow({
                "id": row.get(args.id_col) or f"row_{i + 1}",
                "care_type": resp.care_type,
                "urgency": resp.urgency,
                "red_flags": args.sep.join(resp.red_flags),
                "matched_caregivers": args.sep.join(m.caregiver_id for m in resp.matched_caregivers),
                "scores": args.sep.join(f"{m.score:.2f}" for m in resp.matched_caregivers),
                "reasoning": resp.reasoning,
            })
    print(f"wrote {len(rows)} predictions to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

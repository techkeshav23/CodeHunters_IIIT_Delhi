"""First look at a labelled file: columns, label counts, language mix, examples.

    python -m scripts.eda data/provided/train.csv --text-col text --care-col care_type --urgency-col urgency

Run it the moment the organisers' data lands, before any modelling.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from app.config import CARE_TYPES, URGENCY, internal_label
from app.nlp.normalize import detect_language
from eval.run_eval import load_rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--care-col", default="care_type")
    ap.add_argument("--urgency-col", default="urgency")
    ap.add_argument("--examples", type=int, default=3)
    args = ap.parse_args(argv)

    rows = load_rows(args.path)
    print(f"rows: {len(rows)}")
    if not rows:
        return 1
    print("columns:", list(rows[0].keys()))
    print("first row:", {k: (str(v)[:80]) for k, v in rows[0].items()})

    texts = [str(r.get(args.text_col) or "") for r in rows]
    lengths = sorted(len(t.split()) for t in texts)
    print(f"words per text: median {lengths[len(lengths) // 2]}, max {lengths[-1]}")
    print("languages (our detector):", dict(Counter(detect_language(t) for t in texts)))

    for col, known in ((args.care_col, CARE_TYPES), (args.urgency_col, URGENCY)):
        raw = Counter(str(r.get(col)) for r in rows)
        print(f"\n{col}: {dict(raw.most_common())}")
        unknown = [v for v in raw if internal_label(v) not in known]
        if unknown:
            print(f"  NOT in app/config.py yet (update the label maps): {unknown}")

    if args.care_col in rows[0] and args.urgency_col in rows[0]:
        print("\ncare x urgency:")
        cross = Counter((str(r.get(args.care_col)), str(r.get(args.urgency_col))) for r in rows)
        for (c, u), n in sorted(cross.items()):
            print(f"  {c:>28} | {u:<12} {n}")

    if args.care_col in rows[0]:
        print("\nexamples per care type:")
        seen: Counter = Counter()
        for r in rows:
            c = str(r.get(args.care_col))
            if seen[c] < args.examples:
                seen[c] += 1
                print(f"  [{c} / {r.get(args.urgency_col)}] {str(r.get(args.text_col))[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""External check on CARE-Bench (public, English, patient-facing triage; Hua, Na and Ayubcha,
2026, arXiv 2608.03731, huggingface.co/datasets/ningkko/CARE-Bench).

    python -m scripts.external_carebench data/external/care_bench/evaluation_prefixes_public.jsonl

CARE-Bench labels: 0A info needed, 0B self-care, 1A non-urgent care, 1B urgent/emergency care.
Our labels differ, so this reports what matters for safety:
- urgent recall: 1B cases we send to same-day or immediate care,
- emergency rate on 1B, and false emergencies on 0A/0B/1A,
- how often we ask a question on 0A ("info needed") cases versus the rest.
Used for evaluation only; the data is not redistributed (its GitHub README lists CC BY-NC 4.0).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.config import internal_care, internal_urgency
from app.pipeline import run
from app.schemas import TriageRequest

LOC = {"lat": 28.5459, "lng": 77.2732}


def predict(path: Path, ask: bool = True) -> list[dict]:
    """Our batch decision for every prefix; with `ask`, also whether interactive mode asks first."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for r in rows:
        turns = [str(t) for t in r.get("input_patient_turns") or []]
        if not turns:
            continue
        history = [{"role": "user", "content": t} for t in turns[:-1]]
        req = TriageRequest(user_input=turns[-1], language="en", location=LOC, conversation_history=history)
        batch = run(req, mode="batch")
        inter = run(req, mode="interactive", explain=False) if ask else None
        results.append({
            "prefix_id": r.get("prefix_id"), "gold": r.get("gold_label", "")[:2], "split": r.get("split"),
            "care": internal_care(batch.care_type), "urgency": internal_urgency(batch.urgency),
            "red_flags": batch.red_flags, "asked": inter is not None and inter.follow_up_question is not None,
            "text": " | ".join(turns)[:300],
        })
    return results


def safety_rates(results: list[dict]) -> dict:
    """Urgent (1B) cases sent to same-day or immediate care, and false emergencies on the rest."""
    urgent = [x for x in results if x["gold"] == "1B"]
    rest = [x for x in results if x["gold"] != "1B"]
    return {"urgent_recall": sum(x["urgency"] in ("same_day", "immediate") for x in urgent) / max(1, len(urgent)),
            "false_emergency_rate": sum(x["urgency"] == "immediate" for x in rest) / max(1, len(rest))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--show", type=int, default=25, help="urgent cases we under-triaged to print")
    ap.add_argument("--out", type=Path, default=Path("eval/out/carebench_results.jsonl"))
    args = ap.parse_args(argv)

    results = predict(args.path)

    by_gold: dict[str, list[dict]] = {}
    for x in results:
        by_gold.setdefault(x["gold"], []).append(x)
    print(f"prefixes: {len(results)}  by gold label: { {k: len(v) for k, v in sorted(by_gold.items())} }")
    print("\nour urgency per gold label:")
    for g, xs in sorted(by_gold.items()):
        c = Counter(x["urgency"] for x in xs)
        print(f"  {g}: " + ", ".join(f"{u} {n}" for u, n in c.most_common()))
    urgent = by_gold.get("1B", [])
    if urgent:
        hit = [x for x in urgent if x["urgency"] in ("same_day", "immediate")]
        em = [x for x in urgent if x["urgency"] == "immediate"]
        print(f"\nurgent (1B) sent to same-day or immediate care: {len(hit)}/{len(urgent)} = {len(hit) / len(urgent):.3f}")
        print(f"urgent (1B) sent to emergency: {len(em)}/{len(urgent)} = {len(em) / len(urgent):.3f}")
    rest = [x for g, xs in by_gold.items() if g != "1B" for x in xs]
    if rest:
        fa = [x for x in rest if x["urgency"] == "immediate"]
        print(f"false emergencies on 0A/0B/1A: {len(fa)}/{len(rest)} = {len(fa) / len(rest):.3f}")
    info = by_gold.get("0A", [])
    if info:
        other = [x for x in results if x["gold"] != "0A"]
        print(f"asked a question: 0A {sum(x['asked'] for x in info)}/{len(info)}, "
              f"others {sum(x['asked'] for x in other)}/{len(other)}")

    missed = [x for x in urgent if x["urgency"] == "routine"]
    if missed:
        print(f"\nURGENT CASES WE SENT TO ROUTINE ({len(missed)}), first {args.show}:")
        for x in missed[: args.show]:
            print(f"  {x['prefix_id']}: {x['care']}/{x['urgency']} :: {x['text'][:220]}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in results) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

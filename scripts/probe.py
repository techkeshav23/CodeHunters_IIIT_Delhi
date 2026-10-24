"""Run a JSONL file of test messages through the pipeline and print one JSON line per case.

    python -m scripts.probe eval/out/my_cases.jsonl

Each input line needs "text" (and optionally "id", "history"). Output lines carry
id, care_type, urgency, red_flags, follow_up_question (interactive mode) and reasoning.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.pipeline import run
from app.schemas import TriageRequest

LOC = {"lat": 28.5459, "lng": 77.2732}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    for i, line in enumerate(Path(args[0]).read_text(encoding="utf-8-sig").splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        hist = row.get("history") or []
        req = TriageRequest(user_input=row.get("text", ""), location=LOC, conversation_history=hist)
        batch = run(req, mode="batch")
        inter = run(req, mode="interactive")
        print(json.dumps({
            "id": row.get("id", f"case_{i + 1}"), "care_type": batch.care_type, "urgency": batch.urgency,
            "red_flags": batch.red_flags, "follow_up_question": inter.follow_up_question,
            "reasoning": batch.reasoning,
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

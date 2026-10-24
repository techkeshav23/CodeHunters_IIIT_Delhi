# Model comparison

Same test sets for every system; none of them is used in training.

| System | Organisers 340: care F1 | urgency F1 | emergency recall | false emergency | Hard cases: emergency recall | false alarms | care acc | CARE-Bench urgent>=same_day | p50 ms |
|---|---|---|---|---|---|---|---|---|---|
| Rules only | 1.000 | 1.000 | 1.000 | 0.000 | 1.0 | 0.0 | 0.9239 | 1.0 | 0.7 |
| Rules + TF-IDF/LR (previous) | 1.000 | 1.000 | 1.000 | 0.000 | 1.0 | 0.0 | 0.9239 | 1.0 | 1.8 |
| MuRIL + guardrails (new) | 1.000 | 1.000 | 1.000 | 0.000 | 1.0 | 0.0 | 0.6522 | 1.0 | 19.2 |

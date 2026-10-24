# Model comparison

None of these sets is used to train the model. The organisers' rows are scored as the API answers
them (default policy: ask only when the intent is unclear); the other sets are single messages.

## Fresh blind set (eval/fresh/blind_fresh_v1.jsonl)

150 messages (50 Hinglish, 50 Hindi, 50 English), written for this test by someone who did not
see the rules, the lexicon or the training data. First run, before any change:

| System | Care accuracy | Care macro-F1 | Urgency macro-F1 | Emergency recall | Under-triage |
|---|---|---|---|---|---|
| Rules only | 74.0% | 0.765 | 0.840 | 0.84 | 3 |
| Rules + TF-IDF/LR (previous system) | 74.7% | 0.772 | 0.845 | 0.84 | 3 |
| MuRIL + guardrails | 93.3% | 0.929 | 0.915 | 0.84 | 0 |

Emergency policy, same set (MuRIL + guardrails):

| When the model alone may call 112 | Recall | False alarms | Hand-written look-alikes (false) | CARE-Bench (false) |
|---|---|---|---|---|
| Never (only a named red flag) | 0.84 | 1.6% | 0% | 13.8% |
| Care head ≥ 0.5 | 1.00 | 2.4% | 14.9% | 34.7% |
| Care head ≥ 0.97 | 1.00 | 1.6% | 12.7% | 30.5% |
| **≥ 0.97 and no denied danger sign (deployed)** | **1.00** | **1.6%** | **0–19% per set** | **24.4%** |

The four emergencies the lexicon missed (lip and throat swelling after food, "decided to end
it tonight", a fit while not responding, phenyl drunk by a child) were then added to the
lexicon; after that the served system scores care accuracy 96.0% on this set, which is no
longer blind for the rules.

## Organisers' 340 rows and our hand-written sets

| System | Organisers: care F1 | urgency F1 | emergency recall | false emergency | Hand-written: recall | care agreement | p50 |
|---|---|---|---|---|---|---|---|
| Rules only | 1.000 | 1.000 | 1.000 | 0.000 | 1.0 | 92% | 0.7 ms |
| Rules + TF-IDF/LR | 1.000 | 1.000 | 1.000 | 0.000 | 1.0 | 92% | 1.8 ms |
| MuRIL + guardrails | 1.000 | 1.000 | 1.000 | 0.000 | 1.0 | 65% | 19 ms |

The rules were written and fixed against both of these sets, so they are in-sample for the
rules and new for the model. The hand-written care labels follow our older convention (mild
complaints to a teleconsult); most disagreements are teleconsult vs medic visit at the same
urgency, and there is no under-triage.

# CareCompass: care navigation and caregiver matching

Team CodeHunters (Keshav Upadhyay, Harsh Kumar Sah), HackIIITD 2026, CAI problem statement.
Code: github.com/techkeshav23/CodeHunters_IIIT_Delhi · Live: https://carecompass.145-223-21-27.sslip.io

## 1. Approach

A family member types or speaks a need in English, Hindi or Hinglish. CareCompass returns
the care type, the urgency, any red flags, a plain reason and up to three caregivers, each
with a reason. When the need is unclear it asks a follow-up question. It routes; it never
diagnoses or prescribes. It is one stateless REST API (`POST /v1/triage`, the problem
statement's schema), used by a web app and an Android app.

**Module 1, intake: a fine-tuned model.** MuRIL (Google's BERT for Indian languages,
Roman and Devanagari) is fine-tuned with five heads that share one encoder:
- care type: medic visit, nursing, lab, teleconsult, emergency, follow-up, out of scope;
- urgency;
- red flags;
- structured symptoms and services;
- who the patient is.

It reads the whole conversation, newest turn last. Its probabilities are calibrated
(temperature scaling, ECE 0.045 on held-out families). It is served with ONNX Runtime on
CPU in about 20 ms.

**Module 2, triage: the model decides, with guardrails around it.**
- The danger-sign lexicon (25 types, 800+ phrases, negation-aware) is a safety net. It can
  only escalate.
- 112 is called when a red flag is named. If the model alone senses danger, the app first
  asks about danger signs, and a "Haan" goes to the emergency path.
- Urgency is never below the rules' urgency. It is at least same day for a baby, an older
  adult or a pregnancy.
- Fever goes to an in-person check.
- When the model is unsure, Claude gives a second opinion. It can choose the care type or
  raise an emergency, never remove one.
- Every response lists which guardrails fired (`trace.guardrails`).

**Smart intake questions.** The app asks at most three questions, the danger-sign question
first, with tap-to-answer options in the user's language. It skips anything already said.
The API's default policy asks only when the intent is unclear, as in the organisers' labels.

**Module 3, matching.** The organisers' recipe, which we reproduced from their labels:
- Eligible: the right role, active, the required skill, within the caregiver's radius.
- Score: 0.35 language + 0.30 proximity + 0.20 skill + 0.15 rating.
- Advanced-tier medics are required for IV and catheter care.
- Availability is shown in the reason ("free now till 9 pm").

The user then books in one tap.

## 2. Data, training and why not RAG

The organisers' 340 rows contain only **65 distinct messages** (22 situations × 3
languages), and every emergency is labelled `chest_pain, breathlessness`. A model trained
on them memorises sentences. So we used **teacher → student distillation**:
1. We wrote a labelling guide (`docs/LABELING_GUIDE.md`) from the organisers' conventions
   and public triage guidance (ESI handbook, WHO ETAT).
2. Claude Opus 5.5 wrote 2,743 new messages for 62 case families. The label of each
   family is fixed by us; Claude only writes text.
3. Cleaning: duplicates removed; anything within cosine 0.8 of a test message removed;
   non-emergency messages in which our rules saw a danger sign removed.
4. Augmentation: Roman-script copies, typos and 840 multi-turn conversations, for 4,140
   examples in total.

**The organisers' 340 rows are never used for training: they are the test set.** There is
no retrieval at run time: the model is trained, not a lookup.

## 3. Results (none of these sets is used in training)

| | Score |
|---|---|
| Held-out case families (12 unseen families, incl. chest pain, suicidal, IV drip) | care accuracy 83% |
| Organisers' 340 rows, first model, before any error analysis | care macro-F1 0.966, urgency 0.968, emergency recall 1.0 |
| Organisers' 340 rows, final model alone / served system | 1.0 / 1.0, no false emergencies |
| Our 600 hard cases (negation, minimised symptoms, typos, run-together Devanagari) | emergency recall 1.0, false alarms 0% |
| CARE-Bench public (925 English prefixes) | urgent → at least same day 100%, false emergencies 13.8% |
| Caregiver matching vs the organisers' labels | 209/209 lists and scores, NDCG@3 1.0 |
| Latency (model, CPU) | ~20 ms |

**Read with care.** The organisers' messages are short and clear. After the first model,
we added seven families from its error analysis (reports, mild issues, self-reported fever,
denied danger signs), so the final 1.0 is not blind. The first model's 0.966 and the 83% on
unseen families are the honest generalisation numbers. Training accuracy is 99.6% against
83% on unseen families, so the model fits its families more tightly than new ones; the
guardrails exist for that gap.

**Model comparison** (`scripts/compare_models.py`, `docs/RESULTS_MODELS.md`):
- rules only;
- the previous rules + TF-IDF/logistic regression;
- MuRIL with guardrails;
- MuRIL with guardrails and Claude when unsure.

## 4. Models and APIs used

| Component | What it is |
|---|---|
| Triage model | MuRIL base (google/muril-base-cased, Apache-2.0), fine-tuned here (PyTorch, transformers; RTX 4050, 8 epochs, about 9 min), fp32 ONNX (int8 changed answers, so not used) |
| Teacher | Claude Opus 5.5 (Anthropic API), offline: training text only, about 0.5M tokens (under US$10) |
| Second opinion | Claude Opus 5.5, only when the model is unsure, 8 s timeout. Off without a key; the model alone then answers |
| Safety net, extraction | Team-written lexicon and rules, RapidFuzz |
| Voice | Browser Web Speech API and speechSynthesis; Android speech services in the app |

The code was written during the event, with help from AI coding assistants.

## 5. Safety and privacy

- Red flags skip matching. The emergency screen shows 112, 102 and 108, plus Tele-MANAS
  14416 for self-harm and the poisons centre for poisoning.
- Under-triage is gated: the build fails on any missed emergency or a case routed less
  urgently than its label.
- No medicine or disease names reach the user: a final filter removes them.
- Every non-emergency answer carries safety-netting advice ("if breathing gets hard, call 112").
- Request text is not logged. Claude sees a message only when the model is unsure.
  Bookings stay in memory and on the device.

## 6. Known limitations

- The training text is synthetic. Real families will phrase things we did not imagine, and
  the 83% on unseen families is the realistic expectation for brand-new kinds of request.
- The red-flag heads learned little: emergencies are named by the lexicon. The model's
  emergency sense leads to the danger-sign question, not to 112 by itself.
- Where our old labels chose a teleconsult for mild complaints, the model follows the
  organisers' convention of a home visit.
- English, Hindi and Hinglish only. Not a medical device.

## 7. Data cited

- Sanocare synthetic care-triage dataset v1 (2026): test set and conventions.
- MuRIL (Khanuja et al., 2021).
- CARE-Bench v1.1 (Hua, Na and Ayubcha, 2026, arXiv:2608.03731): evaluation only, CC BY-NC 4.0.
- ESI Implementation Handbook (AHRQ) and WHO ETAT: danger-sign definitions in the labelling guide.
- Our generated data is in `data/generated/`. No real patient information was used.

# CareCompass: care navigation and caregiver matching

Team CodeHunters (Keshav Upadhyay, Harsh Kumar Sah). HackIIITD 2026, CAI problem statement.
Repository: github.com/techkeshav23/CodeHunters_IIIT_Delhi ·
Live: https://carecompass.145-223-21-27.sslip.io

## 1. Approach

A family member types or speaks a request in English, Hindi (Devanagari) or Hinglish.
CareCompass returns the care type (`paramedic_home_visit`, `home_nursing`, `lab_test_home`,
`teleconsultation`, `emergency_112`), the urgency (`scheduled`, `same_day`, `emergency`),
any red flags, a plain reason and up to three caregivers with a reason each, or one
follow-up question when the message is too vague. Labels follow the organisers' dataset.
It routes; it never diagnoses or prescribes.

Every request goes through one pipeline behind a stateless REST API (`POST /v1/triage`,
the problem statement's schema; the client sends the conversation each time):

1. **Normalise.** Devanagari is transliterated (बुखार → "bukhaar") and spellings are reduced
   to a phonetic key, so bukhaar, bukhar and bkhar meet. 287 spellings (WhatsApp short
   forms, English words as speech-to-text writes them in Devanagari) map onto 62 known
   words; text typed without spaces ("saansnahiaarahi", "chestpain") is split back.
2. **Red-flag check first.** 25 red-flag types in 800+ phrases across three languages,
   negation-aware, some only with context ("sust" in a baby, bleeding in pregnancy). Any
   red flag returns `emergency_112` / `emergency` at once: no question, no caregivers.
3. **Understand.** Symptoms, services asked for (injection, dressing, lab test, teleconsult),
   who the patient is, age, pregnancy, duration and severity.
4. **Decide: rules and a learned model together.** The rules give a care type (or "not
   enough to decide"). A model trained on the organisers' data (section 2) runs on every
   request and gives probabilities over paramedic, nursing, lab, doctor, emergency and
   follow-up. When the rules decided, the model overrides them only when it is clearly sure
   (rules vote 0.4, picked on validation); when the rules understood nothing, the model
   decides alone, including "ask first". Urgency follows the care type as in the
   organisers' labels (lab tests scheduled, the rest same day) and never drops below what
   the rules found for a baby, an older adult or severe pain.
5. **Ask only when it matters**, at most three questions with tap-to-answer options in the
   user's language; answers are still checked for red flags.
6. **Match** with the organisers' recipe, which we reproduced from their labels: eligible =
   right role (medic for visits and nursing, phlebotomist for lab tests, doctor for
   teleconsults), active, the skill the request needs, and within the caregiver's own
   radius for home care; score = 0.35 language + 0.30 proximity + 0.20 skill + 0.15 rating.
   Reasons come only from computed facts ("Hindi-speaking, 2.7 km away, free 15:00–21:00").

The problem statement's example ("papa ko do din se bukhar hai aur khansi bhi") returns
`paramedic_home_visit`, `same_day`, no red flags, as in the example.

## 2. Models and APIs used

| Component | What it is |
|---|---|
| Learned triage model | TF-IDF (character 2–5 and word 1–2 n-grams over the normalised tokens, plus tags for recognised services, symptoms and red flags) + multinomial logistic regression, scikit-learn, trained on the organisers' dataset (`scripts/train_triage.py`, `models/triage.joblib`, 206 KB). About 2 ms per message |
| Red flags, extraction, matching | Team-written rules and lexicon (`app/data/lexicon.yaml`), Python, FastAPI |
| Fuzzy spelling match | RapidFuzz (Levenshtein ratio) |
| Voice / read-aloud | Browser Web Speech API (`hi-IN`, `en-IN`) and `speechSynthesis`; the Android app (Flutter, `mobile/`) uses the phone's speech services (Google's engine when installed). Read-aloud speaks the API's Devanagari `trace.speech` and picks the most natural installed voice (neural/online first, old desktop voices last) |
| External LLMs or paid APIs | None at runtime |

**Why this model, and not a transformer or an LLM.** We tested two multilingual transformer
encoders (paraphrase-multilingual-MiniLM-L12-v2 and multilingual-e5-small, int8 ONNX) as
extra features on the same split. They did not help: held-out accuracy of the model alone
went 83% → 78%, and on 88 messages written by other people (our labelled case sets) the
served system scored 86.4% with or without them. With 22 training situations the limit is
the data, not the classifier, so we kept the 206 KB linear model: it trains in seconds,
answers in ~2 ms offline, puts its probabilities in every response (`trace.model`) and
cannot write medical text. An LLM would add seconds per answer, send family health details
to a third party, depend on the network during scoring, and we could not show that it
keeps every emergency.

The code was written during the event with help from AI coding assistants.

## 3. Safety and privacy

- **Red flags before everything**, and the model can add an emergency but never remove
  one or lower urgency. The emergency screen shows 112, 102 (Delhi CATS) and 108, plus
  Tele-MANAS 14416 for self-harm and the AIIMS Poisons Information Centre for poisoning.
- **Negation without losing emergencies.** "saans lene mein koi dikkat nahi" is not a red
  flag; "dard kam nahi ho raha" and "saans nahi aa rahi" are. Past or settled events,
  other people, "if" questions and fears ("stroke na ho") are not counted.
- **No medical advice in text**: a final filter removes medicine and disease names.
- **Robust to data files**: odd caregiver files load row by row; an unreadable one falls
  back to the sample profiles and `/health` says why.
- **Privacy**: request text is not logged or stored; bookings live in server memory and
  on the device.

## 4. Evaluation

**Organisers' dataset, done honestly.** Its 340 rows hold only 66 distinct messages: 22
situations, each in English, Hinglish and Hindi. A random split would put a message or its
translation on both sides, so we split by situation: 6 situations (one per class) are a
test set used once; the other 16 are validated leave-one-situation-out to pick the model's
regularisation and the rules' vote; the deployed model is then refit on all 22.

| | Validation (48 messages) | Test (18 messages, unseen situations) |
|---|---|---|
| Model + rules, as served | 100% | 100% (English, Hinglish and Hindi each 100%) |
| Model alone | 79% | 83% |
| Emergency recall / false emergencies | 100% / 0% | 100% / 0% |

Training, validation and test agree, so the model is neither over- nor under-fitting the
situations it has; "model alone 83%" is its honest generalisation number. Six lexicon
phrases were added after reading this data, so the rules' share of the 100% is partly
in-sample. End to end through the API, all 340 rows match care type, urgency and the 39
follow-up questions. Matching reproduces the labelled caregivers and scores on all 209 rows
that have them (NDCG@3 1.0) and returns none on all 36 non-emergency rows where the labels
have none. One label quirk: the dataset marks every emergency `chest_pain, breathlessness`
even for heavy bleeding or a collapse; we return the specific flag (`severe_bleeding`,
`unconsciousness`).

**Unseen public data: CARE-Bench** (925 English patient-message prefixes, 172 urgent).
Under the organisers' urgency policy only lab tests are "scheduled", so every urgent case
gets at least same-day care; the informative numbers are that 53.5% of urgent cases went
straight to emergency and 13.8% of non-urgent ones were over-triaged to emergency.

**Regression sets** (synthetic, for testing only): 583 tricky messages. First-run recall on
the sets a teammate wrote without seeing our rules was 75%, 39%, 93% and 73% (blind v1 to
v4); after fixes every set catches every emergency with no false alarms, except one blind-v4
message whose label contradicts its own category (40 of 41 caught; reported, not gated).
All sets run in the test suite (182 tests), so their 100% shows coverage, not accuracy on
new data. The build fails if any emergency is missed, if false emergencies pass 10%, or if
a labelled case is routed less urgently than its label. Full numbers: `docs/RESULTS.md`.

To reproduce: `pytest`, `python -m scripts.train_triage`, `python -m scripts.eval_matching`,
`python -m eval.run_eval data/sanocare_v1/triage_dataset.jsonl --mode interactive`.

## 5. Known limitations

- The organisers' data is small and templated (22 situations), so the model alone is right
  on 83% of unseen situations; the rules carry phrasings it has not seen.
- Rules cover the phrasings we and our blind sets thought of; on messages written by other
  people the served system picks the organisers' care type 86% of the time.
- Matching follows the organisers' recipe, which ignores availability except in the reason.
- English, Hindi and Hinglish only; voice quality depends on the device's speech service.
- Not a medical device: it supports a routing decision and always shows a call-for-help path.

## 6. Data and datasets cited

- Sanocare synthetic care-triage dataset v1 (2026), provided for the IIIT-Delhi hackathon
  (`data/sanocare_v1/`): training and evaluation.
- CARE-Bench v1.1 public data (Hua, Na and Ayubcha, 2026, "CARE-Bench: Benchmarking
  Patient-Facing LLM Triage", arXiv:2608.03731): evaluation only, not redistributed (CC BY-NC 4.0).
- Our own test sets are synthetic; no real patient information was collected.
- Open-source components: FastAPI, Pydantic, Uvicorn, PyYAML, RapidFuzz, scikit-learn,
  NumPy, SciPy, joblib, React, Vite, lucide-react, Flutter, Anek and Noto Sans fonts.

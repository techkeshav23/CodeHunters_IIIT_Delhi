# CareCompass: care navigation and caregiver matching

Team CodeHunters (Keshav Upadhyay, Harsh Kumar Sah). HackIIITD 2026, CAI problem statement.
Repository: github.com/techkeshav23/CodeHunters_IIIT_Delhi

## 1. Approach

A family member types or speaks a request in English, Hindi (Devanagari) or Hinglish.
CareCompass returns the care type (paramedic home visit, nurse, GP teleconsult,
specialist, emergency referral), the urgency (routine, same day, immediate), any red
flags, a plain reason, and the three best caregivers with a reason for each. It routes;
it never diagnoses or prescribes.

Every request goes through one pipeline, served by a stateless REST API
(`POST /v1/triage`, the indicative JSON schema; the client sends the conversation each time):

1. **Normalise.** Devanagari is transliterated to Roman (बुखार → "bukhaar") and spellings are
   reduced to a phonetic key, so bukhaar, bukhar and bkhar meet. A table of 287 spellings
   maps WhatsApp short forms (ni, rha, bht) and English words as speech-to-text writes them
   in Devanagari (चेस्ट पेन, सुसाइड) onto 62 known words. Text typed without spaces
   ("saansnahiaarahi", "chestpain") is split back into words.
2. **Red-flag check first.** 25 red-flag types, written as 805 phrases in three languages:
   breathing difficulty, chest pain, stroke signs, unconsciousness, seizures, heavy bleeding,
   major injury, allergy swelling, poisoning, venomous bites, burns, self-harm, psychiatric
   emergency, pregnancy warning signs, danger signs in babies, severe headache, severe
   abdominal pain, dehydration, sudden confusion, low sugar, heat stroke, eye injury, BP of
   180 or more, out-of-range device readings ("oxygen 86", "pulse 38") and a request for an
   ambulance. Some phrases count only with context (for example "sust" in a baby, or
   bleeding in pregnancy). Any red flag returns `emergency_referral` / `immediate` at once,
   with no question and no caregiver matching.
3. **Understand.** Symptoms (32 types), services asked for (14, such as injection, dressing,
   teleconsult), who the patient is (Papa, Dadi, baby), age, pregnancy, duration and severity.
4. **Decide.** Each symptom carries a care type and urgency for a new problem and for one
   lasting two weeks or more; the most urgent wins. Babies, older adults, pregnancy and
   severe pain raise urgency; a mild adult fever goes to teleconsult.
5. **Ask only when it matters.** A question is asked only if the answer can change the
   decision (nothing understood, a child's age when there is fever, duration when it decides
   new versus long-standing), at most three, with tap-to-answer options in the user's
   language. Answers are still checked for red flags ("2 din se, aur ab behosh ho gaye").
6. **Match.** Caregivers with the right role are scored on skill or specialty fit, earliest
   free slot within the urgency window, distance, shared language and rating (Bayesian
   average). Distance counts for home visits and not at all for teleconsults. Caregivers of
   another specialty, outside the visit radius or with no free slot are moved down, not
   hidden. Reasons are built only from computed facts ("Hindi-speaking, 1.6 km away, free at
   4 pm"), so a reason cannot be wrong about the data.

The problem statement's own example ("papa ko do din se bukhar hai aur khansi bhi")
returns exactly the example output: `paramedic_home_visit`, `same_day`, no red flags.

## 2. Models and APIs used

| Component | What it is |
|---|---|
| Triage, red flags, matching | Team-written rules and lexicon (`app/data/lexicon.yaml`), Python, FastAPI |
| Fuzzy spelling match | RapidFuzz (Levenshtein ratio), no learned model |
| Optional learned model | TF-IDF + logistic regression (scikit-learn), blended with the rules. It can raise urgency or add an emergency, never lower the rules' level. Ready to train with `scripts/train_baseline.py`; off, because no doctor-labelled data was released |
| Voice input / read-aloud | Browser Web Speech API (`hi-IN`, `en-IN`) and `speechSynthesis` |
| External LLMs or paid APIs | None at runtime |

**Why no LLM.** We considered fine-tuning or calling a language model and chose not to.
With no labelled clinical data we could not show that it keeps every emergency, its free
text can drift into diagnosis, and a hosted model would send family health details to a
third party and depend on the network during scoring. Fixed rules are slower to write but
every decision can be traced to a phrase and tested.

The code was written during the event with help from AI coding assistants.

## 3. Safety and privacy

- **Red flags before everything.** The emergency path shows 112 (all India), 102 (Delhi
  CATS ambulance) and 108, plus Tele-MANAS 14416 for self-harm and the AIIMS Poisons
  Information Centre (1800-116-117) for poisoning.
- **Negation without losing emergencies.** "saans lene mein koi dikkat nahi" and
  "No weakness, numbness, chest pain or trouble breathing" are not red flags; "dard kam
  nahi ho raha" (pain not easing) and "saans nahi aa rahi" (cannot breathe) are.
  Minimisers ("bas thoda", "gas hogi") never cancel a red flag. Past or settled events,
  other people ("padosi ko heart attack aaya tha"), "if" questions and fears ("stroke na
  ho") are not counted; a chest pain or fall that has settled becomes a same-day check.
- **Under-triage is the costly error.** The optional model can only raise urgency, and
  blend settings are picked only among those that keep every labelled emergency caught.
- **No medical advice in text.** Reasons use symptom labels only; a final filter removes
  medicine names, doses and disease names.
- **Robust to the organisers' files.** A caregiver file in an unexpected shape is read
  row by row; if it cannot be read at all, the API keeps serving from the sample profiles
  and `/health` says why.
- **Privacy.** The API keeps no record of what users type: request text is not logged or
  stored. Bookings live in memory on the server and in the user's browser.

## 4. Evaluation

No labelled vignettes were released. Our honest measure of new data is a public benchmark
we never tuned on; our own sets are regression tests.

**Unseen data: CARE-Bench** (925 English patient-message prefixes, 172 urgent). 87.8% of
urgent cases were sent to same-day or immediate care; 13.7% of non-urgent ones were
over-triaged to emergency; 12% of urgent ones went to routine care. Its labels (info
needed, self-care, non-urgent, urgent) differ from ours, so this is a safety check, not a
routing score.

**Regression sets** (synthetic, written for testing only; 432 cases, 270 emergencies):

| Set | Cases (emergencies) | Emergency recall, first run → now | False emergencies now |
|---|---|---|---|
| Team tricky cases | 122 (81) | 100% | 0% |
| Blind v1, written without seeing the lexicon | 95 (63) | 75.4% → 100% | 0% |
| Blind v2: speech-to-text, low sugar, heat, pregnancy | 85 (41) | 39.0% → 100% | 0% |
| Blind v3: long messages with one buried danger sign | 66 (41) | 92.7% → 100% | 0% (12% first run) |
| Adversarial sweep (built from the misses it found) | 33 (23) | 0% → 100% | 0% |
| Probes of "someone else", "if" and risk talk | 18 (12) | 91.7% → 100% | 0% (1 of 6 first run) |
| Pregnancy cues (8th month, expecting, waters broke) | 13 (9) | 11.1% → 100% | 0% |

Every miss was fixed and all sets run in the test suite (96 automated tests): the build
fails if any emergency is missed, if false emergencies pass 10%, or if any labelled case is
under-triaged. So 100% here shows coverage of what we have seen, not accuracy on new data.
On the 62 labelled ordinary cases, care type matches every label and urgency matches 56 of
57 (the other is one level higher than the label).

**Matching.** No expert rankings were released, so NDCG is not reported. Tests check that
the nearest in-window caregiver who speaks the user's language comes first for a home
visit, that teleconsults ignore distance, that the right specialist comes first (ENT, not
"mental health"; urology, not neurology), and that a caregiver with no free slot is listed
last. Median time inside the pipeline is under 1 ms on a laptop.

To reproduce: `pytest`, `python -m eval.run_eval eval/cases/<set>.jsonl`, and
`python -m scripts.external_carebench <CARE-Bench file>`.

## 5. Known limitations

- Routing rules were set by the team, not learned from doctor labels; borderline cases
  may differ from the organisers' labels.
- `care_type` values for nurse and specialist follow the problem statement's wording
  (`nurse`, `specialist`); only `paramedic_home_visit` appears in its example.
- Rules cover the phrasings we and our blind sets thought of; long, unusual descriptions
  can still be missed, as the 12% of urgent CARE-Bench cases sent to routine care shows.
- Caregiver profiles are 26 mock profiles around IIIT-Delhi; matching weights were set by
  hand, not tuned against expert rankings.
- English, Hindi and Hinglish only. Voice quality depends on the browser's speech service.
- Not a medical device. It supports a routing decision and always shows a call-for-help
  path for emergencies.

## 6. Data and datasets cited

- Synthetic data only; no real patient information was collected or uploaded.
- CARE-Bench v1.1 public data (Hua, Na and Ayubcha, 2026, "CARE-Bench: Benchmarking
  Patient-Facing LLM Triage", arXiv:2608.03731; huggingface.co/datasets/ningkko/CARE-Bench).
  Used for evaluation only, not for training, and not redistributed; its GitHub README lists
  the data as CC BY-NC 4.0.
- Open-source components: FastAPI, Pydantic, Uvicorn, PyYAML, RapidFuzz, scikit-learn,
  NumPy, SciPy, React, Vite, lucide-react, Anek and Noto Sans fonts.

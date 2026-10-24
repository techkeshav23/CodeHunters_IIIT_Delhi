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

1. **Normalise.** Devanagari is transliterated to Roman (बुखार → "bukhaar"), spellings are
   reduced to a phonetic key so bukhaar, bukhar and bkhar meet, 261 aliases cover WhatsApp
   short forms (ni, rha, bht) and English words as speech-to-text writes them in Devanagari
   (चेस्ट पेन, सुसाइड). Text typed without spaces is split back into words.
2. **Red-flag check first.** 24 red-flag types (441 phrases in three languages): breathing
   difficulty, chest pain, stroke signs, unconsciousness, seizures, heavy bleeding, major
   injury, allergy swelling, poisoning, venomous bites, burns, self-harm, pregnancy warning
   signs, danger signs in young babies, severe headache, severe abdominal pain, dehydration,
   sudden confusion, low sugar in diabetics, heat stroke, eye injury, BP of 180 or more, and
   an explicit request for an ambulance. Any red flag returns `emergency_referral` /
   `immediate` straight away, with no follow-up question and no caregiver matching.
3. **Understand.** Symptoms (32 types), services asked for (14, e.g. injection, dressing,
   teleconsult), who the patient is (Papa, Dadi, baby), age, duration and severity.
4. **Decide.** Each symptom carries a care type and urgency for a new problem and for a
   problem lasting two weeks or more; the most urgent wins. Babies, children, older adults,
   pregnancy and severe pain raise urgency; a mild adult fever goes to teleconsult.
5. **Ask only when it matters.** A question is asked only if the answer can change the
   decision (no symptom understood, a child's age when there is fever, duration when it
   decides acute versus chronic), at most three, with tap-to-answer options in the user's
   language. The web app also asks one breathing question for fever or cough.
6. **Match.** Caregivers with the right role are scored on skill fit, earliest free slot
   within the urgency window, distance, shared language and rating (Bayesian average).
   Weights differ by care type: distance counts for home visits and not at all for
   teleconsults. Reasons are built only from computed facts ("Hindi-speaking, 1.6 km away,
   free at 4 pm"), so a reason cannot be wrong about the data.

The problem statement's own example ("papa ko do din se bukhar hai aur khansi bhi")
returns exactly the example output: `paramedic_home_visit`, `same_day`, no red flags.

## 2. Models and APIs used

| Component | What it is |
|---|---|
| Triage, red flags, matching | Team-written rules and lexicon (`app/data/lexicon.yaml`), Python, FastAPI |
| Fuzzy spelling match | RapidFuzz (Levenshtein ratio), no learned model |
| Optional learned model | TF-IDF (character and word n-grams over the normalised tokens) + logistic regression, scikit-learn, blended with the rules; red-flag rules always win and the model can only add emergencies. Ready to train with `scripts/train_baseline.py`; not active because no doctor-labelled training data was released |
| Voice input / read-aloud | Browser Web Speech API (`hi-IN`, `en-IN`) and `speechSynthesis` |
| External LLMs or paid APIs | None at runtime |

The code was written during the event with help from AI coding assistants.

## 3. Safety logic

- **Red flags before everything.** The check runs first and returns the emergency path
  with 112 (all India), 102 (Delhi CATS ambulance) and 108, plus Tele-MANAS 14416 for
  self-harm and the AIIMS Poisons Information Centre (1800-116-117) for poisoning.
- **Negation without losing emergencies.** "saans lene mein koi dikkat nahi" and
  "No weakness, numbness, chest pain or trouble breathing" are not red flags; "dard kam
  nahi ho raha" (pain not easing) and "saans nahi aa rahi" (cannot breathe) are.
  Minimisers ("bas thoda", "gas hogi") never cancel a red flag. Past history ("seizure
  disorder years ago", "pichle saal") is not counted unless the user says it is
  happening now.
- **Under-triage is the costly error.** When the optional model is active, urgency is chosen
  by expected cost with under-triage weighted above over-triage, and blend settings are
  picked only among those that keep every labelled emergency caught.
- **No medical advice in text.** Reasons use symptom labels only; a final filter removes
  medicine names, doses and disease names.

## 4. Evaluation

No labelled vignettes were released, so we built three test sets and used one public
benchmark. Our test sets are synthetic, written by the team, and used for testing only.

| Set | Cases (emergencies) | Emergency recall | False emergencies |
|---|---|---|---|
| Team tricky cases | 122 (81) | 100% | 0% |
| Blind set v1, written without seeing the lexicon | 95 (63) | 75.4% first run → 100% | 0% |
| Blind set v2, speech-to-text, low sugar, heat, pregnancy | 85 (41) | 39.0% first run → 100% | 0% |
| CARE-Bench public prefixes (English, unseen) | 925 (172 urgent) | 87.8% of urgent sent to same-day or immediate care | 13.7% |

Blind-set misses were fixed and both sets now run in the test suite (59 automated tests;
the build fails if any emergency in them is missed), so their 100% shows coverage, not
accuracy on new data. CARE-Bench uses different labels (info needed, self-care, non-urgent,
urgent), so it is a safety check rather than a routing score. Median response time inside
the pipeline is under 1 ms on a laptop.

## 5. Known limitations

- Routing rules were set by the team, not learned from doctor labels; the care type and
  urgency for borderline cases may differ from the organisers' labels.
- `care_type` values for nurse and specialist follow the problem statement's wording
  (`nurse`, `specialist`); only `paramedic_home_visit` appears in its example.
- Rules cover the phrasings we and our blind sets thought of; long, unusual descriptions
  can still be missed. On English CARE-Bench, 12% of urgent cases went to routine care.
- Caregiver profiles are 26 mock profiles around IIIT-Delhi; matching weights were set by
  hand, not tuned against expert rankings.
- Hindi and Hinglish only (plus English); other Indian languages are not supported. Voice
  quality depends on the browser's speech service.
- Not a medical device. It supports a routing decision and always shows a call-for-help
  path for emergencies.

## 6. Data and datasets cited

- Synthetic data only; no real patient information was collected or uploaded.
- CARE-Bench v1.1 public release (Wu et al., 2026, arXiv:2608.03731,
  huggingface.co/datasets/ningkko/CARE-Bench): evaluation only, not used for training and
  not redistributed (no licence is stated).
- Open-source components: FastAPI, Pydantic, Uvicorn, PyYAML, RapidFuzz, scikit-learn,
  NumPy, SciPy, React, Vite, lucide-react, Noto Sans fonts.

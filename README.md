# CareCompass

Care navigation and caregiver matching for HackIIITD 2026 (problem statement by
CAI, IIIT-Delhi). A family member types or speaks a health problem in English,
Hindi or Hinglish; CareCompass decides **what care fits** (paramedic home visit,
nurse, GP teleconsult, specialist or emergency), **how urgent it is** (routine,
same day, immediate) and **who should go** (ranked caregivers with a reason for
each). Any red-flag symptom skips matching and goes straight to call-for-help.

It supports routing decisions only. It does not diagnose or prescribe.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt      # Windows
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Open `http://localhost:8000/docs`. The web app is in `web/` (see `web/README.md`).

With Docker (API on 8000, web app on 5173):

```bash
docker compose up --build
```

## API

`POST /v1/triage` follows the indicative JSON schema from the problem statement.
Full contract and examples: [`docs/API.md`](docs/API.md), [`docs/examples/`](docs/examples/).

```bash
curl -X POST http://localhost:8000/v1/triage -H "Content-Type: application/json" \
  -d '{"user_input": "papa ko do din se bukhar hai aur khansi bhi", "language": "auto",
       "location": {"lat": 28.54, "lng": 77.27}, "conversation_history": []}'
```

```json
{
  "follow_up_question": null,
  "care_type": "paramedic_home_visit",
  "urgency": "same_day",
  "red_flags": [],
  "reasoning": "Fever with cough for 2 days; no breathing difficulty reported, so a same-day paramedic home visit fits.",
  "matched_caregivers": [{"caregiver_id": "DEV_CG_003", "score": 0.88, "reason": "Hindi-speaking, 1.6 km away, free at 4 pm, fever care experience"}]
}
```

Other endpoints: `POST /v1/bookings`, `GET /v1/labels`, `GET /health`.
The API is stateless: the client sends the conversation each time.

## How it works

```
text / voice
 -> normalise: Devanagari transliterated, Hinglish spellings reduced to phonetic keys
 -> red-flag rules (English, Hindi, Hinglish; negation-aware) -- hit --> emergency, no matching
 -> extract: symptoms, services asked for, who the patient is, age, duration, severity
 -> triage rules (care type + urgency)    [optional learned model: can only raise urgency, off by default]
 -> follow-up question only if the answer can change the decision (max 3; answers re-checked for red flags)
 -> caregiver ranking: role filter, then skill, free time, distance, language, rating
 -> response with reasons built only from computed facts
```

Safety logic:

- Red flags come from `app/data/lexicon.yaml` (to be aligned with the organisers'
  care taxonomy and reviewed by the clinical mentors). A red flag is never
  answered with a question; it returns `immediate` with call-for-help numbers
  (112, Delhi ambulance 102, 108; Tele-MANAS 14416 for self-harm; AIIMS poisons
  centre 1800-116-117).
- Negation is handled ("saans lene mein koi dikkat nahi" is not a red flag), but
  phrases like "dard kam nahi ho raha" (pain not reducing) are not treated as negation,
  and minimisers ("bas thoda", "gas hogi") never cancel a red flag.
- Reasoning text never names a disease or a medicine (`text.scrub` as a last guard).

## Evaluation

```bash
.venv\Scripts\python -m eval.run_eval eval\cases\redteam_v0.jsonl
.venv\Scripts\python -m pytest
```

`eval/run_eval.py` reports macro-F1 for care type and urgency, emergency recall,
false alarms, under-triage, NDCG@3 for matching (when labels exist) and latency.
`eval/cases/` holds 511 synthetic tricky cases (313 emergencies): casual
emergencies, negations, Devanagari, typos, run-together words, babies, pregnancy,
mental health, other people's or past events, and look-alikes. They are for
testing only, not training, and their care/urgency labels are the team's own,
not doctors'.

| Set | Cases | Written by |
|---|---|---|
| `redteam_v0` | 122 | backend side |
| `redteam_blind_v1`, `_v2`, `_v3` | 95, 85, 66 | second team member, without seeing the lexicon (first runs caught 75%, 39% and 93% of emergencies) |
| `redteam_sweep_v1` | 33 | adversarial sweep, built from the misses it found |
| `redteam_probe_v1`, `redteam_pregnancy_v1` | 18, 13 | probes of suppression rules and pregnancy cues |
| `redteam_review_v1` | 79 | review of our own fixes (look-alikes, run-together words, other apps' questions) |

Every miss was fixed and all sets are in the test suite, so they are regression
sets now. `pytest` fails if any emergency is missed, if false emergencies pass
10%, or if a labelled case is under-triaged (`tests/test_safety.py`,
`tests/test_routing.py`).

External check on public data: [CARE-Bench](https://huggingface.co/datasets/ningkko/CARE-Bench)
(Hua, Na and Ayubcha, 2026, arXiv:2608.03731; English, 925 labelled patient-message prefixes;
CC BY-NC 4.0 per its GitHub README, so it is used for evaluation only and not included in this repo):

```bash
.venv\Scripts\python -m scripts.external_carebench data\external\care_bench\evaluation_prefixes_public.jsonl
```

On 24 Oct 2026: 87.8% of CARE-Bench "urgent care" cases were sent to same-day or
immediate care, and 13.5% of non-urgent cases were over-triaged to emergency.
CARE-Bench labels (info needed, self-care, non-urgent, urgent) differ from ours,
so this is a safety check, not a routing score.

Predictions file for the hidden test set:

```bash
.venv\Scripts\python -m scripts.predict_csv data\provided\test.csv --out predictions.csv
```

## Data

All data is synthetic. Organiser files go in `data/provided/` (git-ignored).
Until the organisers' caregiver profiles are there, matching uses
`app/data/dev_caregivers.json`: 26 mock profiles written by the team around
IIIT-Delhi, labelled DEV.

## Models and APIs used

- Rules and lexicon written by the team; RapidFuzz for spelling distance.
- Optional TF-IDF + logistic regression model (`scripts/train_baseline.py`), off until
  doctor-labelled data exists; it can only raise urgency.
- No LLM and no paid API at runtime (see `docs/WRITEUP.md` for why).
- Voice in the web app: the browser's Web Speech API.

## Open-source components

FastAPI, Starlette, Pydantic, Uvicorn (MIT / BSD), PyYAML (MIT), RapidFuzz (MIT),
scikit-learn, NumPy, SciPy, joblib (BSD), pytest (MIT), httpx (BSD).
Web app packages are listed in `web/README.md`.

## Project layout

```
app/            API, pipeline, NLP, triage rules, matching
app/data/       lexicon.yaml (red flags, symptoms, services), dev caregivers
eval/           metrics, eval harness, tricky test cases
scripts/        predictions CSV, CARE-Bench check, probe, optional model training
tests/          pytest suite
docs/           API contract, examples, write-up, web app spec
web/            web app (Vite + React)
```

Code written during HackIIITD 2026 (24-25 Oct 2026), with help from AI coding assistants.

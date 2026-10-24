# Raahat (राहत)

![Raahat logo](web/public/icon-192.png)

*Ek message, aur raahat ghar tak.* Our product for the CareCompass problem statement.

Care navigation and caregiver matching for HackIIITD 2026 (problem statement by
CAI, IIIT-Delhi). A family member types or speaks a health problem in English,
Hindi or Hinglish; Raahat decides **what care fits** (paramedic home visit,
nurse, GP teleconsult, specialist or emergency), **how urgent it is** (routine,
same day, immediate) and **who should go** (ranked caregivers with a reason for
each). Any red-flag symptom skips matching and goes straight to call-for-help.

It supports routing decisions only. It does not diagnose or prescribe.

Live demo: https://carecompass.145-223-21-27.sslip.io (web app; the API is on the same
origin, for example `/health`, `/v1/triage`, `/docs`). Synthetic data only.

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

On a shared server behind its own HTTPS reverse proxy, `docker-compose.server.yml`
keeps both containers on 127.0.0.1 (API 8000, web 8001), with memory limits and restart;
the web container passes `/v1`, `/health` and `/docs` to the API, so the site and a
mobile app use one HTTPS address:

```bash
docker compose -f docker-compose.server.yml up -d --build
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
text / voice (+ the conversation so far)
 -> MuRIL, fine-tuned (app/triage/student.py, ONNX, ~20 ms): care type, urgency, red flags,
    structured symptoms, who the patient is; calibrated confidence (high / medium / low)
 -> safety net: the danger-sign lexicon (English, Hindi, Hinglish; negation-aware) can only escalate;
    a named red flag -> emergency_112, no matching; the model alone sensing danger -> danger-signs question
 -> guardrails: urgency never below the rules', at least same day for a baby / older adult / pregnancy,
    fever gets a home check; model unsure -> Claude second opinion (optional) or a question
 -> follow-up questions (app: up to 3, danger signs first, tap-to-answer; API default: only when unclear)
 -> caregiver matching (organisers' recipe): role, active, skill, tier, radius; 0.35 language + 0.30 proximity + 0.20 skill + 0.15 rating
 -> response with reasons built only from computed facts
```

Safety logic:

- Red flags come from `app/data/lexicon.yaml`. A red flag is never answered with a
  question and the model cannot remove it; it returns `emergency_112` / `emergency` with call-for-help numbers
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
`eval/cases/` holds 583 synthetic tricky cases (354 emergencies): casual
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
| `redteam_blind_v4` | 72 | second team member, blind again, with 21 multi-turn histories (first run caught 73%) |

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

On 24 Oct 2026, with the organisers' labels (only lab tests are scheduled): every urgent
CARE-Bench case got at least same-day care, 53.5% went straight to emergency, and 13.8%
of non-urgent cases were over-triaged to emergency.
CARE-Bench labels (info needed, self-care, non-urgent, urgent) differ from ours,
so this is a safety check, not a routing score.

Predictions file for the hidden test set:

```bash
.venv\Scripts\python -m scripts.predict_csv data\provided\test.csv --out predictions.csv
```

## Data

All data is synthetic. The organisers' dataset (Sanocare synthetic care-triage dataset
v1, redistributable for the event) is in `data/sanocare_v1/`: 340 labelled requests
(66 distinct messages, 22 situations in three languages) and a 60-caregiver roster, which
is the default matching pool (`/health` shows `caregivers_source: sanocare_v1`). Other
files can go in `data/provided/` (git-ignored); `app/data/dev_caregivers.json` is the
team's 26-profile sample, used only as a fallback.

Training text for the model is synthetic, written by Claude Opus 5.5 for 62 case families
whose labels we fixed (`docs/LABELING_GUIDE.md`, `data/generated/`). The organisers' 340 rows
are never trained on; they are the test set.

Train and check (GPU training uses a separate venv with CUDA PyTorch and transformers):

```bash
.venv\Scripts\python -m scripts.gen_data                             # teacher writes messages (ANTHROPIC_API_KEY)
.venv-train\Scripts\python -m scripts.train_student                  # prepare, held-out families, final training
.venv-train\Scripts\python -m scripts.train_student --export-only    # ONNX + test on the organisers' rows
.venv\Scripts\python -m scripts.compare_models                       # rules vs TF-IDF vs MuRIL
.venv\Scripts\python -m scripts.eval_matching                        # caregiver lists vs the labels
```

The model weights (`models/student/model.onnx`, about 950 MB) are too big for git: they are
published as a GitHub release asset (`model-muril-v3`); put `model.onnx` into
`models/student/` next to `meta.json` and `tokenizer.json`, or rebuild it with the two
commands above. Without it the API falls back to the rules and the older TF-IDF model.

## Models and APIs used

- MuRIL base (google/muril-base-cased, Apache-2.0), fine-tuned by us; served with ONNX Runtime.
- Claude Opus 5.5 (Anthropic API): offline teacher that wrote the training text; at run time
  only a second opinion when the model is unsure (`CC_LLM_FALLBACK=on` and `ANTHROPIC_API_KEY`).
- Danger-sign lexicon and rules written by the team (the safety net); RapidFuzz for spelling.
- The previous TF-IDF + logistic regression model (`scripts/train_triage.py`) is the fallback.
- Voice: the browser's Web Speech API; the Android app uses the phone's speech services.

## Open-source components

FastAPI, Starlette, Pydantic, Uvicorn (MIT / BSD), PyYAML (MIT), RapidFuzz (MIT),
scikit-learn, NumPy, SciPy, joblib (BSD), pytest (MIT), httpx (BSD), ONNX Runtime (MIT),
Hugging Face tokenizers and transformers (Apache-2.0), PyTorch (BSD), anthropic SDK (MIT).
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

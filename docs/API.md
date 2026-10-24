# CareCompass API

Base URL (local): `http://localhost:8000`; live: `https://carecompass.145-223-21-27.sslip.io`.
Interactive docs: `/docs`.

This follows the problem statement's schema, with the label values of the organisers'
dataset (Sanocare synthetic care-triage dataset v1, `data/sanocare_v1/README.md`). All
outward-facing values live in `app/config.py`.

The API is **stateless**: the client sends the whole conversation every time.

---

## POST /v1/triage

Alias: `POST /triage`.

Query parameters: `explain=true` adds `trace` (below); `policy` picks how follow-up questions
are asked: `minimal` (default, used by the organisers' scorer: decide directly when the
message is clear, ask only when the intent is unclear or a child's age is needed), `safety`
(minimal plus a breathing check for fever and cough) or `conversational` (the web and the
app; see "Conversational policy").

### How a decision is made

When the fine-tuned model (MuRIL, `models/student/`) is loaded, the API is **model-first**:

1. The lexicon still reads the facts (duration, age, answers to our questions). Its red-flag
   rules are the **safety net**: they can only escalate.
2. **Emergency** if the rules find a red flag, or the model's red-flag head fires, or its
   emergency / "immediate" probability passes its threshold. `red_flags` is the union of both.
3. Otherwise the model's top care type. Its `followup` class asks what is needed;
   `out_of_scope` answers with a polite scope message (`q_scope`). When the model is unsure
   (confidence band `low`): Claude gives a second opinion if switched on, else the
   conversational policy asks a question, else the rules' choice, else the model's.
4. **Urgency** is the model's, never `emergency` outside the emergency path, never below
   the rules' urgency, at least `same_day` for a baby, an older adult or a pregnancy (an
   older adult's own lab test stays `scheduled`), and `scheduled` for a home lab test unless
   one of these raises it.

Without the model file (CI, `CC_STUDENT=off`) the rules + the older TF-IDF model decide as
before. `trace.decision.source` says which: `model`, `model+safety_net` (the model, with the
rules adding a red flag or raising urgency), `safety_net` (the rules decided: a red flag the
model missed, an answer of "Haan" to the danger question, or the model was unsure), `llm`
(Claude's second opinion) or `rules` (the fine-tuned model is not loaded; `model` there
means the older TF-IDF model).

### Request

```json
{
  "user_input": "papa ko do din se bukhar hai aur khansi bhi",
  "language": "auto",
  "location": { "lat": 28.54, "lng": 77.27 },
  "conversation_history": []
}
```

| Field | Type | Notes |
|---|---|---|
| `user_input` | string | The newest message. When answering a follow-up question, this is the answer ("Haan", "Nahi", "2 din", free text). |
| `language` | string | `auto` (default), `en`, `hi`, `hinglish`. |
| `location` | `{lat, lng}` or null | Needed for home-visit distance. |
| `conversation_history` | list | Earlier turns, oldest first, **not** including `user_input`. |

`conversation_history` items we accept:

```json
[
  { "role": "user", "content": "Papa ki tabiyat theek nahi hai" },
  { "role": "assistant", "content": "Unhe kya taklif ho rahi hai?", "question_id": "q_main_symptom" },
  { "role": "user", "content": "bukhar hai" },
  { "role": "assistant", "content": "Kya saans lene mein dikkat ho rahi hai?", "question_id": "q_breathing" }
]
```

`question_id` is optional but please send it back when the question came from
`trace.follow_up.id`; it makes answer parsing exact. Plain strings and
`{"question": ..., "answer": ...}` pairs are also accepted.

### Response

Exactly these six fields (indicative schema):

```json
{
  "follow_up_question": null,
  "care_type": "paramedic_home_visit",
  "urgency": "same_day",
  "red_flags": [],
  "reasoning": "Fever with cough for 2 days; no breathing difficulty reported, so a same-day paramedic home visit fits.",
  "matched_caregivers": [
    { "caregiver_id": "DEV_CG_003", "score": 0.91, "reason": "Hindi-speaking, 2.1 km away, free at 4 pm" }
  ]
}
```

Three shapes:

| Situation | `follow_up_question` | `care_type` / `urgency` | `red_flags` | `matched_caregivers` |
|---|---|---|---|---|
| Final decision | `null` | set | `[]` | top 3, best first |
| Needs more info | question text (user's language) | `null` | `[]` | `[]` |
| Emergency | `null` | `emergency_112` / `emergency` | non-empty | `[]` (matching is skipped) |

Rules the backend guarantees:

- A red flag never gets a follow-up question; it goes straight to the emergency shape.
- At most 3 follow-up questions per conversation (`CC_MAX_FOLLOWUPS`).
- `reasoning` and `reason` never name a disease or a medicine.

### Labels (the organisers' values)

| Internal key | `care_type` value | `urgency` that goes with it |
|---|---|---|
| paramedic | `paramedic_home_visit` | `same_day` |
| nurse | `home_nursing` | `same_day` |
| lab | `lab_test_home` | `scheduled` |
| gp, specialist | `teleconsultation` (a department, if any, is in `trace.decision.specialty`) | `same_day` |
| emergency | `emergency_112` | `emergency` |

`urgency`: `scheduled`, `same_day`, `emergency` (internally routine, same_day, immediate).
Urgency never goes below what the rules found (a baby, an older adult, severe pain).
Files with the earlier values (`nurse`, `gp_teleconsult`, `specialist`,
`emergency_referral`, `routine`, `immediate`) are still read correctly.

`red_flags` uses the organisers' vocabulary where it has the flag: `chest_pain`,
`breathlessness`, `unconsciousness`, `severe_bleeding`, `stroke_symptoms`, `seizure`,
`high_fever_infant` (our danger signs in a young baby), `suicidal_ideation`,
`severe_dehydration`. Flags their list does not have keep our id: `major_injury`,
`severe_allergy`, `poisoning`, `venomous_bite`, `severe_burn`, `psychiatric_emergency`,
`pregnancy_emergency`, `severe_headache`, `severe_abdominal_pain`, `sudden_confusion`,
`low_sugar_signs`, `heat_stroke`, `eye_injury`, `severe_bp`, `abnormal_vitals`
(pulse, oxygen, BP, sugar or child temperature numbers out of range),
`emergency_requested`, `possible_emergency` (an emergency with no particular sign named:
the model alone, or "Haan" to the danger question) and `other_emergency` (the fine-tuned
model's "other emergency" class: poisoning, snake bite, severe burn...). The two generic
ones are dropped when a specific flag is also present.
`trace.red_flags[].id` always holds our id, with labels in three languages; labels for
each come from `GET /v1/labels`. `trace.red_flags[].source` says who raised it: `rules`,
`model`, `rules+model` or `llm`.

`trace.model` (when a learned model is loaded):

```json
"model": {
  "name": "MuRIL (fine-tuned)",
  "probabilities": { "paramedic": 0.93, "nurse": 0.01, "lab": 0.01, "gp": 0.03, "emergency": 0.01, "followup": 0.005, "out_of_scope": 0.005 },
  "urgency_probabilities": { "routine": 0.04, "same_day": 0.95, "immediate": 0.01 },
  "confidence": 0.93,
  "band": "high",
  "flags": [],
  "version": "2026-10-24T20:00:00",
  "latency_ms": 18.2
}
```

`confidence` is the calibrated probability of the top care class; `band` is `high`, `medium`
or `low` (thresholds in the model's `meta.json`). With the older TF-IDF model only `name`,
`probabilities` (without `out_of_scope`) and `version` are present.

`trace.llm` (only when Claude's second opinion was used): `{model, care_type, urgency,
red_flags, reasoning, latency_ms}`. It is off unless `CC_LLM_FALLBACK=on` and
`ANTHROPIC_API_KEY` are set (`CC_LLM_MODEL`, default `claude-opus-5-5`; 8 s timeout, one
retry; any error is ignored). It is asked only when the model is unsure and did not say
emergency, and it can only pick a care type or add an emergency, never remove one.

`trace.speech`: what the apps read aloud, `{"locale": "hi-IN" | "en-IN", "text": ...}`. For
Hindi and Hinglish it is the Hindi (Devanagari) wording, because a Hindi voice reads
Roman-script Hindi with English sounds; phone numbers are spaced digit by digit ("1 1 2").

---

## POST /v1/triage?explain=true (for the web app)

Same request. The response has the six fields above **plus** `trace`, which the
web app uses for the "what we understood", "why", follow-up buttons, emergency
screen and caregiver cards. `*_local` strings are in the user's language
(`trace.language`: `en`, `hi` = Devanagari, `hinglish` = Roman Hindi).

```json
"trace": {
  "version": "0.1.0",
  "language": "hinglish",
  "understood": {
    "patient": { "relation": "father", "relation_label": "Papa", "age_years": null, "age_group": null, "pregnant": null },
    "symptoms": [
      { "id": "fever", "label": "Fever", "label_local": "Bukhar" },
      { "id": "cough", "label": "Cough", "label_local": "Khansi" }
    ],
    "duration_days": 2,
    "duration_label": "2 days",
    "services": [],
    "severity": []
  },
  "checks": [
    { "id": "breathing_difficulty", "label": "Breathing difficulty", "label_local": "Saans lene mein dikkat", "status": "not_reported" }
  ],
  "red_flags": [],
  "decision": {
    "care_type": "paramedic_home_visit",
    "urgency": "same_day",
    "care_label": "Paramedic home visit",
    "care_label_local": "Paramedic ghar aakar check karenge",
    "urgency_label": "Today",
    "urgency_label_local": "Aaj hi",
    "confidence": 0.74,
    "source": "rules",
    "rule": "acute_fever"
  },
  "reasoning_local": "2 din se bukhar aur khansi, saans ki dikkat nahi batayi. Aaj ek paramedic ghar aakar check karenge.",
  "follow_up": null,
  "emergency": null,
  "caregivers": [
    {
      "caregiver_id": "DEV_CG_003",
      "name": "Ravi Kumar",
      "role": "paramedic",
      "languages": ["Hindi", "English"],
      "skills": ["vitals check", "fever care"],
      "distance_km": 2.1,
      "next_slot": "2026-10-24T16:00:00+05:30",
      "next_slot_label": "today 4 pm",
      "next_slot_label_local": "aaj 4 baje",
      "rating": 4.8,
      "score": 0.91,
      "reason": "Hindi-speaking, 2.1 km away, free at 4 pm",
      "reason_local": "Hindi bolte hain, 2.1 km door, aaj 4 baje free"
    }
  ],
  "speech": {"locale": "hi-IN", "text": "2 दिन से बुखार और खांसी, सांस की दिक्कत नहीं बताई। आज एक पैरामेडिक घर आकर जाँच करेंगे।"},
  "timing_ms": 9.4
}
```

`checks[].status`: `present`, `absent` (user said no), `not_reported`.

Also stable (added after v0): `trace.mode` (`interactive` / `batch`),
`trace.decision.specialty` (for example `orthopaedics`, or null), and
`trace.caregivers[].features`: the 0-1 sub-scores behind each match
(`skill`, `time`, `distance`, `language`, `rating`), good for a small
"why this caregiver" breakdown. `trace` is present on every shape when
`explain=true`.

The default policy (`minimal`, used for automated scoring) only asks when the
answer is needed to decide. `policy=safety` adds a breathing check for fever
and cough cases.

### New trace fields (all optional; older responses lack them)

`trace.structured`: Module 1's structured intake, on every shape.

```json
"structured": {
  "symptoms": [
    { "id": "fever", "label": "Fever", "label_local": "Bukhar" },
    { "id": "cough", "label": "Cough", "label_local": "Khansi" }
  ],
  "who": "elderly",
  "who_label": "Older adult",
  "who_label_local": "Buzurg",
  "duration_days": 3,
  "age_years": 70
}
```

`symptoms` are the model's tags (symptoms and services) followed by anything else the
lexicon found. `who`: `self`, `adult`, `elderly`, `child`, `infant`, `pregnant` or `unknown`
(from the words first: age, pregnancy, "dadi"; else the model). `duration_days` and
`age_years` come from the words and the answers, or null.

`trace.guardrails`: every check, on every shape, in this order, with `status` `fired` when
it changed or decided something and `pass` otherwise.

```json
"guardrails": [
  { "id": "safety_net", "label": "Danger-sign rules", "label_local": "Khatre ke lakshan ke niyam",
    "status": "pass", "note": "No danger sign found in the words used.",
    "note_local": "Likhi baat mein koi khatre ka lakshan nahi mila." }
]
```

| id | fired when |
|---|---|
| `safety_net` | the rules found a red flag (or "Haan" to the danger question) |
| `model_emergency` | the model said emergency |
| `vulnerable_floor` | urgency raised to `same_day` for a baby, an older adult or a pregnancy |
| `urgency_floor` | urgency raised to the rules' urgency |
| `low_confidence` | the model's band was `low` |
| `out_of_scope` | the message is not about home health care |
| `llm_fallback` | Claude's second opinion was used |
| `clinical_scope` | a disease or medicine name was removed from the reply |
| `invariants` | the final contract check had to correct the response |

`trace.safety_net_local`: on a final non-emergency decision, when to come back or call 112,
in the user's language (null on questions and emergencies). Example (Hinglish, fever):
"Agar saans lene mein dikkat, seene mein dard, behoshi, ya bukhar 3 din se zyada rahe, to
turant 112 par call karein ya hamein batayein."

### Conversational policy (`policy=conversational`, the web and the app)

A short check-up before deciding, at most 3 questions (`CC_MAX_FOLLOWUPS`), never when a
red flag is present, skipping anything already known:

1. Intent unclear: `q_main_symptom` (what is needed). Not about health care: `q_scope`.
2. A symptom (medic visit or doctor consult): `q_danger` first (danger signs, options
   Haan / Nahi), then `q_duration` if the duration is unknown, then `q_who` (or `q_age`
   for a child) if who and how old is unknown.
3. A service request (injection, dressing, lab test): no danger or duration questions.
4. When the model is unsure and nothing else is left to ask: `q_main_symptom`.
5. Still unclear when the questions run out: `teleconsultation`, `same_day` (safe default).

"Haan" to `q_danger` goes straight to the emergency shape with `possible_emergency`
(a named sign in the answer, "haan, saans phool rahi hai", gives that flag instead). "Nahi"
also counts as no breathing difficulty. "Pata nahi" / "don't know" counts as unknown.

Question ids that may appear in `trace.follow_up.id`: `q_main_symptom`, `q_age`,
`q_duration`, `q_breathing`, and new: `q_danger` (`yes_no`), `q_who` (`choice`: adult, 60 or
older, child, baby 3-12 months, baby under 3 months, pregnant) and `q_scope` (`free_text`,
the polite scope reply: "Hum sirf ghar pe health care mein madad karte hain: doctor se baat,
ghar pe check-up, nursing ya lab test. Kya koi beemar hai?").

`trace.follow_up` when a question is asked:

```json
"follow_up": {
  "id": "q_breathing",
  "text": "Kya saans lene mein dikkat ho rahi hai?",
  "kind": "yes_no",
  "options": [
    { "value": "yes", "label": "Haan" },
    { "value": "no", "label": "Nahi" },
    { "value": "unknown", "label": "Pata nahi" }
  ],
  "asked_so_far": 1,
  "max": 3
}
```

`kind`: `yes_no`, `choice` (tap one option) or `free_text` (options are quick
suggestions; the user may also speak or type). To answer, send the option
`label` (or typed text) as `user_input`, and append the question to
`conversation_history` as `{"role": "assistant", "content": <text>, "question_id": <id>}`.

`trace.emergency` when it is an emergency:

```json
"emergency": {
  "title": "This may be an emergency",
  "title_local": "Yeh emergency ho sakti hai",
  "numbers": [
    { "label": "Emergency (all India)", "label_local": "Emergency (poore Bharat mein)", "number": "112" },
    { "label": "Ambulance in Delhi (CATS, free)", "label_local": "Delhi ambulance (CATS, free)", "number": "102" },
    { "label": "Ambulance in many states", "label_local": "Kai rajyon mein ambulance", "number": "108" }
  ],
  "steps": ["Call 112 now.", "Stay with the patient.", "Keep your phone on and share your location."],
  "steps_local": ["Abhi 112 par call karein.", "Mareez ke saath rahein.", "Phone chalu rakhein aur location share karein."]
}
```

Flag-specific helplines (Tele-MANAS 14416 for `self_harm_risk`, AIIMS poisons
centre 1800-116-117 for `poisoning`) are added to `numbers` when relevant.

Ready-made examples: `docs/examples/`.

---

## POST /v1/bookings

Mock booking (in memory; resets when the server restarts).

```json
// request
{ "caregiver_id": "DEV_CG_003", "slot": "2026-10-24T16:00:00+05:30", "care_type": "paramedic_home_visit", "urgency": "same_day", "note": "" }

// response 201
{ "booking_id": "BK_7F3A2C", "status": "confirmed", "caregiver_id": "DEV_CG_003", "caregiver_name": "Ravi Kumar", "slot": "2026-10-24T16:00:00+05:30", "created_at": "2026-10-24T12:40:00+05:30" }
```

404 if the caregiver id is unknown.

## GET /v1/labels

Care types, urgency levels, red-flag labels (English and Hindi) and emergency
numbers, for clients that want to render them.

## GET /health

`{"status": "ok", "version": "0.1.0", "caregivers_source": "dev_sample", "caregivers": 26, "model": "rules", "model_trained_at": null, "model_test_accuracy": null, "student": null, "llm_fallback": false}`

`model` is `student (MuRIL)` when the fine-tuned model is loaded (then `model_trained_at` and
`model_test_accuracy`, its care accuracy on the organisers' 340 rows, are the student's, and
`student` holds `{name, trained_at, test_organiser_340, holdout, thresholds}` from its
`meta.json`), `rules+model` with the older TF-IDF model, `rules` with neither.
`llm_fallback` says whether Claude's second opinion is switched on.

`caregivers_source` is `provided` (a file in `data/provided/`), `env` (`CC_CAREGIVERS`),
`dev_sample`, or `dev_sample_fallback: <reason>` when the given file could not be read.

---

## Errors

`422` for a malformed request (for example `lat` out of range). Error bodies
follow FastAPI's default `{"detail": [...]}`.

CORS is open for local development (the web app runs on `http://localhost:5173`).

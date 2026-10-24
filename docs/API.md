# CareCompass API (v0 contract)

Base URL (local): `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.

This follows the indicative schema in the problem statement. The organisers
publish the final schema with the dataset; when it lands, only the label values
and field names in `app/config.py` / `app/schemas.py` change. Label values
marked *TBC* are placeholders until then.

The API is **stateless**: the client sends the whole conversation every time.

---

## POST /v1/triage

Alias: `POST /triage`.

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
| Emergency | `null` | `emergency_referral` *TBC* / `immediate` | non-empty | `[]` (matching is skipped) |

Rules the backend guarantees:

- A red flag never gets a follow-up question; it goes straight to the emergency shape.
- At most 3 follow-up questions per conversation (`CC_MAX_FOLLOWUPS`).
- `reasoning` and `reason` never name a disease or a medicine.

### Labels

| Internal key | `care_type` value |
|---|---|
| paramedic | `paramedic_home_visit` |
| nurse | `nurse_home_visit` *TBC* |
| gp | `gp_teleconsult` *TBC* |
| specialist | `specialist_consult` *TBC* |
| emergency | `emergency_referral` *TBC* |

`urgency`: `routine`, `same_day`, `immediate` (`immediate` *TBC*).

Red flag ids (stable): `breathing_difficulty`, `chest_pain`, `stroke_signs`,
`unconscious`, `seizure`, `severe_bleeding`, `major_injury`, `severe_allergy`,
`poisoning`, `venomous_bite`, `severe_burn`, `self_harm_risk`,
`pregnancy_emergency`, `infant_danger_sign`, `severe_headache`,
`severe_abdominal_pain`, `severe_dehydration`, `sudden_confusion`. Labels for
each come from `GET /v1/labels`.

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

The web app sends `policy=safety`, which adds a breathing check for fever
and cough cases. The default (`minimal`, used for automated scoring) only
asks when the answer is needed to decide.

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

`{"status": "ok", "version": "0.1.0", "caregivers_source": "dev_sample", "caregivers": 24, "model": "rules"}`

---

## Errors

`422` for a malformed request (for example `lat` out of range). Error bodies
follow FastAPI's default `{"detail": [...]}`.

CORS is open for local development (the web app runs on `http://localhost:5173`).

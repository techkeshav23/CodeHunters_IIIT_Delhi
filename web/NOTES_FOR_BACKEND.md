# Notes for the backend

How the web app uses the contract, plus anything I need from the API. I build
against `docs/API.md` and `docs/examples/*.json` only.

## What the web app sends

- `POST {VITE_API_BASE}/v1/triage?explain=true` for every turn.
- Request: `{ user_input, language: "auto", location: {lat,lng}, conversation_history }`.
  `conversation_history` is oldest-first and does **not** include the new
  `user_input`. After a response with a `follow_up_question`, I append
  `{role:"user", content:<sent text>}` and
  `{role:"assistant", content:<question>, question_id:<trace.follow_up.id>}`.
- Follow-up answers: I send the tapped option's `label` (or typed/spoken text)
  as `user_input`.
- `POST {VITE_API_BASE}/v1/bookings` with
  `{ caregiver_id, slot: <trace caregiver next_slot>, care_type, urgency, note }`.
- `GET /health` polled every 20s to show the status dot (only when not mocking).

## What the app reads from the response

- Routing: `trace.decision.care_label_local` (headline) +
  `trace.decision.urgency_label_local` (badge). Badge colour keys off
  `trace.decision.urgency` ∈ {routine, same_day, immediate}.
- Emergency: shown when `trace.emergency != null` **or** `red_flags` non-empty.
  Uses `emergency.title_local`, `numbers[]`, `steps_local[]`, and
  `trace.red_flags[].label_local` + `evidence`.
- Explain panel: `trace.understood` (patient/relation_label, symptoms.label_local,
  duration_label, services), `trace.checks[].{status,label_local}`,
  `trace.reasoning_local`.
- Caregiver cards: `trace.caregivers[]` — name, role, languages, distance_km,
  next_slot_label_local (falls back to next_slot_label), rating, reason_local.

## Assumptions / things to confirm

1. **`trace` is always present** on `?explain=true`, including for the
   follow-up and emergency shapes. The app leans on `trace` heavily.
2. `trace.decision.urgency` values are exactly `routine` / `same_day` /
   `immediate`. Badge styling maps on these strings; unknown values fall back to
   the "routine" style.
3. For follow-ups, `trace.follow_up.id` is the `question_id` I echo back. The
   app also tolerates it being absent.
4. Booking response includes `caregiver_name`, `booking_id`, `slot`. If the
   caregiver id is unknown you return 404 — the app shows a retry message.
5. CORS allows `http://localhost:5173` (dev) for `/v1/triage`, `/v1/bookings`,
   `/health`.
6. `*_local` strings are already in the user's language; the app never
   translates API text. I send `language: "auto"` and let the backend decide.

Nothing blocking so far — the mock mode mirrors the three example shapes, so
switching to the live backend should be a matter of flipping `VITE_USE_MOCKS=0`.

---

## Progress

### M1 — all five screens on mocks (done)
- Works end to end on mocks (`VITE_USE_MOCKS=1`): Home → follow-up (2 steps) →
  result with caregiver cards → booking done; and Home → emergency.
- Header on every screen: app name, language switch (हिंदी / Hinglish / English),
  status dot, always-visible red **112** button (`tel:112`). Footer disclaimer
  present. i18n wired for all three languages with localStorage persistence.
- `npm run build` passes with no TypeScript errors; `npm run dev` serves on 5173.
- Explainability ("Kyon?") panel, judge view (API request/response + timing),
  and voice in/out are all implemented in this pass too (ahead of M3).
- **Not yet:** verified against the live backend — waiting on :8000
  (`VITE_USE_MOCKS=0`). Will report any contract mismatch here under M2.

### M2 — live integration verified (done, 2026-10-24)
Switched the UI to the live backend (`VITE_API_BASE=http://127.0.0.1:8000`,
`VITE_USE_MOCKS=0`) and send `?explain=true&policy=safety` (one constant in
`api.ts`). Ran all 11 scenarios from the backend agent's table by replaying the
exact requests the UI makes (turn-by-turn `conversation_history`). **All 11 pass,
no contract mismatches, no oddities.** Notes:
- `/health` → `caregivers: 26` (matches). `127.0.0.1` used (not `localhost`) per
  the IPv6 heads-up — works.
- Follow-up `q_breathing` fires for fever/cough and English cough (policy=safety),
  as intended; "Nahi"/"no" → routes on, "Haan" → `breathing_difficulty` emergency.
- Emergencies all return `matched_caregivers: []` and the emergency trace block;
  `self_harm_risk` adds `14416`, numbers otherwise `[112,102,108]`.
- `trace.decision.specialty` = `orthopaedics` for the knee-pain case; null elsewhere.
- `trace.caregivers[].features` carries exactly 5 sub-scores (skill, time,
  distance, language, rating) — will render these as bars in Task 2.
- Booking: valid → 201 with `caregiver_name`; unknown id → 404 (UI shows retry).
- No code change needed on either side for M2. ✅

### M3/M4 — explainability extras (done, 2026-10-24)
- Each caregiver card now has a "Yeh match kyon" toggle showing the five
  `trace.caregivers[].features` (skill, time, distance, language, rating) as
  small labelled bars with `role="meter"` + percentages. Collapsed by default.
- `trace.decision.specialty` shown as a chip on the decision card when present
  (e.g. "Visheshgya: Orthopaedics"). Only rendered when the API sends it.
- Read-aloud now resets its button state from the real `speechSynthesis` `onend`
  event (no more timeout guess).
- Types added: `MatchFeatures` and `decision.specialty` in `src/types.ts`.
  Both optional, so no break if a field is missing.

### Update 3 — care_type rename (done, 2026-10-24)
- New `care_type` values `nurse` and `specialist` (were `nurse_home_visit` /
  `specialist_consult`): **no frontend label-map change needed** — the UI shows
  `trace.decision.care_label_local` for the headline and passes `care_type`
  straight through to `/v1/bookings`, so it is value-agnostic.
- Mocks: added `triage_nurse.json` and `triage_specialist.json` (captured from
  the live API, so they carry the new values + `features` + `specialty`). Mock
  selection now routes injection/insulin → nurse and ghutne/knee/joint →
  specialist, so all five care types are demoable with `VITE_USE_MOCKS=1`.
- New red-flag ids (`low_sugar_signs`, `heat_stroke`, `eye_injury`, `severe_bp`,
  `possible_emergency`) need no UI change: the emergency screen renders
  `trace.red_flags[].label_local` + `evidence` generically. `possible_emergency`
  may have empty `evidence` — the UI already guards for that.
- `npm run build` clean.

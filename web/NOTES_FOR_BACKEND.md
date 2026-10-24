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

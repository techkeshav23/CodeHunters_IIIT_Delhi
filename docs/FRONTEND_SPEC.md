# CareCompass web app: build spec

You are building the **web front end** of CareCompass for the HackIIITD 2026
finale (problem statement by CAI, IIIT-Delhi). The backend (FastAPI, in `app/`)
is being built at the same time by someone else in this same folder. You talk
to it only through the HTTP contract in `docs/API.md`.

Read first: this file, then `docs/API.md`, then the JSON files in `docs/examples/`.

## 1. What the product does

A family member types or speaks a health problem in Hindi, English or Hinglish
("Papa ko do din se bukhar hai aur khansi bhi"). The app may ask 1 to 3 short
follow-up questions, then shows:

- **what kind of care fits** (paramedic home visit, nurse, GP teleconsult, specialist, or emergency),
- **how urgent** (routine, today, now),
- **the best 3 caregivers** with a plain reason for each, and one-tap booking.

If the backend detects a red flag (for example chest pain), the app shows an
**emergency screen** with call-for-help numbers instead of booking.

Users include elderly and low-literacy people: minimal typing, voice input,
read-aloud, big buttons, plain words.

How the UI is judged: "UX and demo" (20/100: ease of use, multilingual and
voice support, clarity of the end-to-end flow) and "Explainability" (10/100:
clear, correct reasons for every routing and matching decision). A system that
misses emergencies cannot win, so the emergency screen must be impossible to miss.

## 2. Hard rules

1. **Only create or edit files inside `web/`.** Do not touch `app/`, `eval/`,
   `tests/`, `docs/`, `.venv/`, or root files (`.gitignore`, `README.md`,
   `docker-compose.yml`). If you need an API change, write it in
   `web/NOTES_FOR_BACKEND.md` and carry on with a workaround.
2. **Write all code now, during the event.** Do not copy code from other
   projects. npm packages are fine; list each one with its licence in `web/README.md`.
3. **No medical advice in the UI.** Never write diagnoses, medicine names or
   first-aid steps yourself. Show only what the API returns, plus the fixed
   texts in this spec.
4. **Git:** do not commit unless the user asks. If asked, `git add web` only.
   Never run `git reset`, `git checkout -- .`, `git stash` or `git clean`: the
   other half of the team has uncommitted work in this folder.
5. Ports: web dev server **5173**, backend **8000**. Do not start anything on 8000.
6. No analytics, no external network calls other than the API. Bundle fonts
   with npm (`@fontsource/...`), the venue Wi-Fi may be bad.

## 3. Stack (decided)

- Vite + React + TypeScript, in `web/` (`npm create vite@latest web -- --template react-ts`).
- Plain CSS with CSS variables (one `src/styles.css` or CSS modules). No CSS framework.
- Icons: `lucide-react`. Fonts: `@fontsource/noto-sans` and `@fontsource/noto-sans-devanagari`.
- Config via env: `VITE_API_BASE` (default `http://localhost:8000`), `VITE_USE_MOCKS` (`1` = use mocks).
- Suggested files: `src/api.ts` (fetch + mocks), `src/i18n.ts` (all UI strings),
  `src/voice.ts` (speech in/out), `src/screens/*.tsx`, `src/mocks/*.json`.

## 4. Screens and flow

**Persistent header** on every screen: app name, language switch
(हिंदी / Hinglish / English), backend status dot (`GET /health`), and a small
red "112" call button (`tel:112`) that is always visible.

1. **Home (ask).** One big round mic button ("Bolkar batayein"), a text box
   under it ("Ya yahan likhein...", with an example), a Send button, and 2 or 3
   example chips the user can tap ("Papa ko 2 din se bukhar aur khansi",
   "Dadi ko ghar pe injection lagwana hai", "Seene mein dard ho raha hai").
   A location line: "Location: Okhla, New Delhi (demo)" using
   `{lat: 28.5459, lng: 77.2732}` by default, with "Use my location"
   (browser geolocation, optional).
2. **Follow-up question.** When the response has `follow_up_question`: show the
   question very large, read it aloud automatically if the user used voice,
   and show `trace.follow_up.options` as big buttons. Keep the mic and the
   text box for free answers. Show progress ("Sawaal 1 / 3").
3. **Result (non-emergency).** A decision card: `trace.decision.care_label_local`
   as the headline and an urgency badge (`urgency_label_local`). Under it a
   "Kyon?" panel (see section 6). Then up to 3 caregiver cards: name, role,
   languages, distance, next free time, rating, `reason_local`, and a big
   "Book karein" button. A "Sunaiye" (read aloud) button reads the headline,
   the reason and the first caregiver.
4. **Booking done.** `POST /v1/bookings` with the caregiver id and `next_slot`.
   Show caregiver name, time, booking id, and "Naya sawaal" (start over).
5. **Emergency.** When `trace.emergency` is not null (or `red_flags` is
   non-empty): full red screen, `emergency.title_local`, one huge `tel:112`
   button, the other `emergency.numbers` as smaller `tel:` buttons, then
   `emergency.steps_local` as a short numbered list, then which red flags were
   found (`trace.red_flags[].label_local` and `evidence`). **No booking and no
   caregiver cards on this screen.** A small "Naya sawaal" link at the bottom.

Footer on every screen (small but readable): "Demo: sirf synthetic data. Yeh
medical salah nahi hai. Emergency mein 112 par call karein."

**Judge view:** a collapsible panel at the bottom of the result, follow-up and
emergency screens, "API request / response", showing the last request and
response JSON (pretty-printed, with a copy button) and `trace.timing_ms`.
Collapsed by default.

## 5. Conversation handling (stateless API)

Keep `history` in React state. After each response that has a follow-up:

```ts
history = [...history,
  { role: "user", content: sentText },
  { role: "assistant", content: res.follow_up_question, question_id: res.trace.follow_up.id }];
```

The next request sends the answer as `user_input` and `conversation_history: history`.
For an option button, send the option `label` as the text. Final or emergency
response = conversation over; "Naya sawaal" clears everything.

Always call `POST {VITE_API_BASE}/v1/triage?explain=true`. Send
`language: "auto"`. While waiting show "Samajh rahe hain...". On a network
error show a friendly message with a retry button (and the 112 button stays visible).

## 6. Explainability panel ("Kyon?")

- **Humne kya samjha:** chips from `trace.understood`: patient
  (`relation_label`, age if known), each symptom `label_local`,
  `duration_label`, services.
- **Humne kya check kiya:** `trace.checks` with an icon per `status`
  (present = red, absent = green tick, not_reported = grey question mark) and `label_local`.
- **Faisla kyon:** `trace.reasoning_local`.
- Per caregiver: `reason_local` on the card.

## 7. Voice

- Speech to text: Web Speech API (`window.SpeechRecognition ||
  window.webkitSpeechRecognition`). `lang = "hi-IN"` for हिंदी/Hinglish UI,
  `"en-IN"` for English. Show the live transcript in the text box so the user
  can fix it before sending. Stop after a pause. If unsupported (Firefox,
  some Safari), hide the mic and show "Voice Chrome mein chalta hai".
- Text to speech: `speechSynthesis`, pick a voice whose `lang` starts with
  `hi` for Hindi/Hinglish text and `en` for English; slightly slow rate (0.9).
- The mic button must show clear states: idle, listening (pulsing), processing.

## 8. Language

All UI strings live in `src/i18n.ts` with three languages: `hi` (Devanagari),
`hinglish` (Roman Hindi, default) and `en`. Remember the choice in
`localStorage` (wrap in try/catch). Text that comes from the API (`*_local`,
questions) is already in the user's language: show it as is. Starter strings:

| Key | hinglish | hi | en |
|---|---|---|---|
| tagline | Batayein kya taklif hai, hum sahi madad dhoondhenge | बताइए क्या तकलीफ़ है, हम सही मदद ढूँढेंगे | Tell us what is wrong, we will find the right help |
| speak | Bolkar batayein | बोलकर बताइए | Speak |
| type | Ya yahan likhein... jaise: Papa ko 2 din se bukhar hai | या यहाँ लिखिए... जैसे: पापा को 2 दिन से बुखार है | Or type here... e.g. My father has had fever for 2 days |
| send | Bhejein | भेजिए | Send |
| listening | Sun rahe hain... | सुन रहे हैं... | Listening... |
| thinking | Samajh rahe hain... | समझ रहे हैं... | Understanding... |
| why | Kyon? | क्यों? | Why? |
| understood | Humne kya samjha | हमने क्या समझा | What we understood |
| checked | Humne kya check kiya | हमने क्या जाँचा | What we checked |
| book | Book karein | बुक करें | Book |
| booked | Booking ho gayi | बुकिंग हो गई | Booked |
| read | Sunaiye | सुनाइए | Read aloud |
| restart | Naya sawaal | फिर से शुरू करें | Start over |
| call112 | 112 par call karein | 112 पर कॉल करें | Call 112 |

## 9. Look and feel

- Mobile first. On a laptop, centre a phone-width column (max 480px) so the demo looks like the app.
- Body text at least 18px, headlines 26 to 32px, buttons at least 56px tall, generous spacing.
- High contrast (WCAG AA at least). Calm palette (deep blue or teal on off-white).
  **Red only for emergencies** and the 112 button.
- One main action per screen. No dense grids, no gradient blobs, no tiny grey
  uppercase labels, no emoji decoration. It should feel like a simple, trustworthy
  Indian health app, not a developer dashboard.
- Use `lang="hi"` on elements with Devanagari text; give icon buttons `aria-label`s;
  announce results with `aria-live="polite"`.

## 10. Mocks (so you are never blocked)

Copy `docs/examples/*.json` into `web/src/mocks/`. With `VITE_USE_MOCKS=1`,
`api.ts` returns:

- the emergency example if the text mentions seena/seene/chest/saans nahi/behosh,
- the follow-up example (turn 1, then turn 2) if the text has no known symptom word ("tabiyat theek nahi"),
- otherwise the final example,
- and a fake booking response.

Add a 400 ms delay so loading states show. The backend should be live within
about two hours; then run with `VITE_USE_MOCKS=0`. To start it yourself (do not
edit it): from the repo root run `.venv\Scripts\python -m uvicorn app.main:app --port 8000`.

## 11. Done means

- [ ] `npm run build` passes with no TypeScript errors; `npm run dev` serves on 5173.
- [ ] Full journey works with mocks: ask → follow-up → result → booking → done; and ask → emergency.
- [ ] Same journey works against the live backend (`VITE_USE_MOCKS=0`) once it is up.
- [ ] Voice input works in Chrome for Hindi and English; read-aloud works.
- [ ] Emergency screen: `tel:112` reachable in one tap, no booking anywhere on it.
- [ ] Looks right at 360px wide and on a laptop; no horizontal scroll.
- [ ] Language switch changes all UI text; API text shown as is.
- [ ] Network error shows a retry message; no console errors in the normal flow.
- [ ] `web/Dockerfile` (multi-stage: node build, then nginx serving `dist/`, build arg `VITE_API_BASE`).
- [ ] `web/README.md`: how to run, env vars, packages used with licences.

## 12. Milestones

1. **M1 (about 1.5 h):** all five screens working on mocks, i18n, header with 112.
2. **M2:** switch to the live backend; report any contract mismatch in `web/NOTES_FOR_BACKEND.md`.
3. **M3:** voice in and out, explainability panel, judge view.
4. **M4:** polish, accessibility pass, Dockerfile, README.

After each milestone, write 3 to 5 lines in `web/NOTES_FOR_BACKEND.md` under a
"Progress" heading: what works, what does not, what you need.

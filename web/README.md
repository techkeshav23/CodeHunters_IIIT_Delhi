# CareCompass — web front end

The family-facing web app for CareCompass (HackIIITD 2026 finale). A person
describes a health problem in Hindi / English / Hinglish (typed or spoken); the
app asks 1–3 short follow-ups if needed, then shows the right kind of care, how
urgent it is, the best 3 caregivers with a plain reason each, and one-tap
booking. Red-flag symptoms route to a full-screen emergency view instead.

Built with Vite + React + TypeScript. Talks to the backend only through the
HTTP contract in [`../docs/API.md`](../docs/API.md).

## Run it

```bash
cd web
npm install

# Mock mode (no backend needed) — this is the default in .env
npm run dev            # http://localhost:5173

# Against the live backend on :8000
#   set VITE_USE_MOCKS=0 in .env (or the shell), then:
npm run dev
```

Build and preview the production bundle:

```bash
npm run build          # type-checks then builds to dist/
npm run preview
```

To run the backend yourself (do not edit it), from the repo root:

```bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

## Environment variables

Set in `web/.env` (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_BASE` | `http://localhost:8000` | Backend base URL. |
| `VITE_USE_MOCKS` | `1` | `1` = use bundled mock responses, `0` = call the live backend. |

Mock mode picks a response from the user's text (spec §10): emergency words →
emergency; a vague opener (no symptom word) → the 2-step follow-up flow;
anything else → the final result. A fake booking is returned too, with a 400 ms
delay so loading states are visible.

## Docker

Multi-stage build (Node build → nginx serving `dist/`). The backend URL is
baked in at build time:

```bash
docker build --build-arg VITE_API_BASE=http://localhost:8000 -t carecompass-web web
docker run -p 5173:80 carecompass-web   # open http://localhost:5173
```

## Project layout

```
web/
  src/
    api.ts            fetch + mock responses
    i18n.ts           all UI strings (hi / hinglish / en)
    voice.ts          speech-to-text + text-to-speech (Web Speech API)
    useDictation.ts   mic hook shared by the text boxes
    types.ts          API contract types
    App.tsx           state machine + routing between screens
    screens/          Home, FollowUp, Result, Booking, Emergency
    components/       Header, Footer, MicButton, Explain, JudgeView
    mocks/            copies of docs/examples/*.json
```

## Accessibility & design notes

- Mobile-first; on a laptop a phone-width column (max 480px) is centred.
- Body text ≥18px, buttons ≥56px tall, WCAG-AA contrast, calm teal palette.
  **Red is used only for emergencies and the 112 button.**
- Voice input works in Chrome (Web Speech API); the mic hides where unsupported.
  Read-aloud uses `speechSynthesis` at a slightly slow rate.
- Devanagari text is marked `lang="hi"`; icon buttons have `aria-label`s;
  results announce with `aria-live="polite"`.
- No medical advice is written by the UI — only API text plus the fixed strings
  in the spec. No analytics, no network calls other than the API. Fonts are
  bundled via npm (`@fontsource/...`) so bad venue Wi-Fi does not matter.

## npm packages and licences

| Package | Licence | Use |
|---|---|---|
| react, react-dom | MIT | UI framework |
| vite, @vitejs/plugin-react | MIT | build tool / dev server |
| typescript | Apache-2.0 | type checking |
| lucide-react | ISC | icons |
| @fontsource/noto-sans | OFL-1.1 (font), MIT (package) | Latin UI font |
| @fontsource/noto-sans-devanagari | OFL-1.1 (font), MIT (package) | Devanagari UI font |
| @types/react, @types/react-dom | MIT | type definitions |

All code in `src/` was written for this event; no code was copied from other
projects.

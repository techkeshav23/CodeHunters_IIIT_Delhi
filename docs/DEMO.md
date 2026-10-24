# Demo script (3 minutes)

For the finale demo and the video. Written for the current web app (desktop portal with
a sidebar; phone view with a bottom tab bar). Every input below was run on the live API
and in the web app on 24 Oct; the outcomes are what they returned.

## Before you start

1. API: `.venv\Scripts\python -m uvicorn app.main:app --port 8000`, then open
   `http://127.0.0.1:8000/health` and check `"status": "ok"`. Do not restart it mid-demo.
2. Web: `cd web`, `npm run dev`, open `http://localhost:5173` in Chrome. The status line
   in the sidebar should say **Seva chalu hai**.
3. Allow the microphone once (click the mic, then Allow). Say one Hindi and one English
   sentence to check it.
4. For read-aloud in Hindi, Windows needs a Hindi voice (Settings, Time & language,
   Speech). Without one it reads in English; do not wait on it.
5. Language starts on **Hinglish**. Keep these ready to paste if the mic fails:
   - `Mummy ke seene mein dard hai aur pasina aa raha hai`
   - `दो महीने से घुटने में दर्द है`
   - `Mere bete ko bukhar hai`
6. Between flows, press **Nayi jaanch**.

## The run

### 0:00 to 0:15. Open on Jaanch
**Show:** the start screen, "Batayein, kya taklif hai?", the mic, the chips, the red
**112 par call** in the sidebar.
**Say:** "A family member describes the problem in Hindi, English or Hinglish, by typing
or speaking. CareCompass says what care fits, how soon, and who should come."

### 0:15 to 1:00. The problem statement's own example
**Do:** click the example **Papa ko do din se bukhar hai aur khansi bhi**.
**Show:** one question, **Kya saans lene mein dikkat ho rahi hai?** (Sawaal 1 / 3).
**Say:** "Fever and cough, so it checks one danger sign before deciding."
**Do:** tap **Nahi**.
**Show:** the dial on **Aaj hi**, "Paramedic ghar aakar check karenge", and three medics
from the organisers' roster: Sunita Chauhan first (Hindi, 1.3 km, free 08:00–13:00).
**Do:** open **Yeh faisla kyon?** (what we understood: Papa, Bukhar, Khansi, 2 din se;
what we checked: breathing, Nahi hai), then **Match kaise hua** on the first medic (language, distance, skill, rating bars),
and the "Model" line (the trained model's confidence in this decision).
**Say:** "Every decision and every match shows its reason. Caregivers are ranked exactly
as in the organisers' labels, and a model trained on their data agrees with this call."
**Do:** **Book karein**, then **Pakki karein**.
**Show:** "Booking pakki ho gayi" with a booking number. Close it with **Band karein**.

### 1:00 to 1:30. An emergency
**Do:** **Nayi jaanch**, then speak or type `Mummy ke seene mein dard hai aur pasina aa raha hai`.
**Show:** the full-screen emergency: "Yeh emergency ho sakti hai", a large **112**
button, 102 and 108, what to do until help comes, and "Humein kya dikha: Seene mein
dard ya dabav" with the words it matched.
**Say:** "A danger sign skips every question and every booking. Missing an emergency
is the one mistake this app must not make."

### 1:30 to 2:00. Hindi and a specialist
**Do:** **Wapas**, **Nayi jaanch**, switch the language to **हिंदी**, then speak or type
`दो महीने से घुटने में दर्द है`.
**Show:** "डॉक्टर से फ़ोन / वीडियो पर बात", **विभाग: हड्डी और जोड़ (Orthopaedics)**, and
three doctors who consult by video. Tap **सुनाइए** to hear it.
**Say:** "The whole app switches to Hindi, names the department, and can read the answer
aloud. Doctors in the roster consult by video, so distance does not count for them."

### 2:00 to 2:25. A question that can change everything
**Do:** switch back to **Hinglish**, **Nayi jaanch**, type `Mere bete ko bukhar hai`.
**Show:** **Bachche ki umar kitni hai?** Tap **3 mahine se kam**.
**Show:** emergency: a danger sign in a young baby.
**Say:** "It asks only when the answer can change the decision. Fever in a baby under
three months is an emergency, so it asks the age."

### 2:25 to 2:50. For the judges
**Do:** open **Kaise kaam karta hai** in the sidebar.
**Show:** the steps, "583 mushkil test messages, har emergency pakdi", 209/209
caregiver matches, and the last API request and response with the time in ms.
**Say:** "This is the exact API call behind the screen: the problem statement's JSON
schema, answered in a few milliseconds, with no outside AI service."

### Spare examples (all checked on the live server)
- `dadi ko bedsore dressing chahiye` → home nursing, today, three medics with wound dressing.
- `Want a CBC and thyroid test with home sample collection` → lab test at home, scheduled,
  three sample collectors.
- `help chahiye` → one question asking what is needed, with tap options.
- Avoid injection requests at the default location: the organisers' roster has no medic
  with the IM-injection skill near Okhla, so the answer (correctly, as in their labels) has
  no caregivers.

### 2:50 to 3:00. Close
**Say:** "Three languages, voice in and out, a reason for every decision, and an
emergency path you cannot miss."

## If something goes wrong

- **Laptop setup fails:** use the live site https://carecompass.145-223-21-27.sslip.io
  (same app and API, HTTPS, so the mic works in Chrome). On a phone, Chrome's menu offers
  "Install app" for a home-screen icon.

- **Mic does not hear:** type the same text; the result is identical.
- **Read-aloud is silent:** no Hindi voice on the laptop. Say so and move on.
- **API down:** restart it with the command above; the web app shows a retry button on
  the failed message. As a last resort set `VITE_USE_MOCKS=1` in `web/.env` and restart
  `npm run dev` (fever, chest pain, knee pain and injection work on sample data).
- **Phone view:** in Chrome DevTools pick a phone size. The sidebar becomes a top bar and
  a bottom tab bar (Jaanch, Bookings, SOS, Jaankari, Settings).

## Likely questions

- **"Where is the AI? Did you train an LLM?"** No. With no labelled clinical data we
  could not prove an LLM keeps every emergency, its text can drift into diagnosis, and a
  hosted model would send family health details outside. We built a normaliser for
  Hinglish, Devanagari and speech-to-text, a negation-aware red-flag engine and a scoring
  ranker, and tested them on 583 tricky messages, the organisers' dataset and an unseen public benchmark.
  A learned model is wired in but off until doctor-labelled data exists, and it can only
  raise urgency.
- **"How do you know it generalises?"** We split the organisers' data by situation (all three
  languages of a message on one side), so the test set is situations the model never saw: 100%
  with rules, 83% for the model alone. On 88 messages written by other people the system picks
  the organisers' care type 86% of the time; that is our main known gap, and it comes from the
  data (22 situations), which is why a bigger transformer model did not help when we tried it.
- **"Why not an LLM?"** Seconds per answer, health details sent to a third party, network needed
  during scoring, and no way to prove it never misses an emergency. Our model answers in ~2 ms
  offline and shows its probabilities in every response.
- **"What if the organisers' caregiver file looks different?"** Field names are mapped
  loosely (id or caregiver_id, location or lat/lng, lists or comma text); a file that
  cannot be read falls back to the sample profiles and `/health` says why.
- **"Is user data stored?"** No request text is logged or stored. Bookings live in
  server memory and in the browser.

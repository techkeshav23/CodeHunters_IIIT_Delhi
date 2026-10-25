# Demo script (3 minutes)

For the finale demo and the video. Written for the current web app (desktop portal with
a sidebar; phone view with a bottom tab bar). Every input below was run on the live API
and in the web app on 24 Oct, and the flows below again on 25 Oct after the danger checks
became one button per sign; the outcomes are what they returned. Testers replayed all four
flows on the live site on the morning of 25 Oct and got the same results. To start the
next flow, press **Nayi chat** on the answer card or **+ Nayi chat** at the top of the chat
list in the sidebar (behind ☰ on a phone; in the Android app, at the top next to History and
Incognito).

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
6. Between flows, press **Nayi chat**.

Checklist, on the laptop you will present from:

- [ ] **Window at least 1500 px wide.** Below 1500 px the right-hand **Yeh faisla kyon?**
      panel is hidden (only the toggle under the card is left); at 1020 px or less the
      sidebar shrinks to icons and **112 par call** and **Seva chalu hai** disappear. Check
      on a rehearsal decision that the panel shows on the right. If not (125% or 150%
      display scaling, a projector, or DevTools docked to the side), close DevTools and zoom
      Chrome out (Ctrl and minus) until it does.
- [ ] **Clear old chats and bookings** after the last rehearsal. Chats: **Saari history
      mitayein** in the sidebar's chat list, then confirm. That keeps bookings, and old
      ones can show the same medic twice at one time with a stale "kal", so in the DevTools
      console run `localStorage.removeItem("cc_bookings"); location.reload()`.
- [ ] **Run before 1 pm, or expect "kal".** Sunita Chauhan, the first medic in the main
      flow, is free 08:00–13:00. After 1 pm she is still first but her card says "kal subah
      8 baje" under an **Aaj hi** dial (say so, and point to Manoj Das under **Aur 2
      dekhein**, free today until 7 pm); the knee flow's first doctors go to "kal" after
      4 pm. Run the flows 30 minutes before presenting and say what the cards actually show.
- [ ] **Tap every answer button; do not speak the answers.** Speak or type only the first
      message. A spoken "inmein se kuch nahin" is not read as the button and adds an extra
      age question.

## The run

### 0:00 to 0:15. Open on Jaanch
**Show:** the start screen, "Batayein, kya taklif hai?", the mic, the chips, the red
**112 par call** in the sidebar.
**Say:** "A family member describes the problem in Hindi, English or Hinglish, by typing
or speaking. Raahat says what care fits, how soon, and who should come."

### 0:15 to 1:00. The problem statement's own example
**Do:** click the example **Papa ko do din se bukhar hai aur khansi bhi**.
**Show:** one question, **Bukhar ke saath kya inme se kuch hai?** with one button per danger
sign (Saans phoolna ya tez chalna, Bahut susti, Jhatke) and **Inme se kuch nahi** (Sawaal 1 / 3).
**Say:** "Fever and cough, so it checks the danger signs that fit a fever before deciding."
**Do:** tap **Inme se kuch nahi**.
**Show:** the dial on **Aaj hi**, "Paramedic ghar aakar check karenge", and the best medic
from the organisers' roster: Sunita Chauhan (Hindi, 1.3 km; before 1 pm her card says she
is free now). Tap **Aur 2 dekhein** for the other two, Naveen Sharma and Manoj Das.
**Do:** point to **Yeh faisla kyon?** in the right-hand panel (what we understood: Papa,
Bukhar, Khansi, 2 din se; what we checked: breathing, Nahi hai), then **Match kaise hua** on
the first medic (language, distance, skill, rating bars), and the "Model" line ("MuRIL model
ne tay kiya · Pakka bharosa": the trained model is sure of this call).
**Say:** "Every decision and every match shows its reason. Caregivers are ranked exactly
as in the organisers' labels, and a model never trained on their rows agrees with this call."
**Do:** **Book karein**, then **Pakki karein**.
**Show:** "Booking pakki ho gayi" with a booking number. Close it with **Band karein**.

### 1:00 to 1:30. An emergency
**Do:** **Nayi chat**, then speak or type `Mummy ke seene mein dard hai aur pasina aa raha hai`.
**Show:** the full-screen emergency: "Yeh emergency ho sakti hai", a large **112**
button, 102 and 108, what to do until help comes, and "Humein kya dikha: Seene mein
dard ya dabav" with the words it matched.
**Say:** "A danger sign skips every question and every booking. Our danger-sign lexicon,
in three languages, catches it, and nothing can override it; the model routes everything
else. Missing an emergency is the one mistake this app must not make."

### 1:30 to 2:00. Hindi and a doctor on video
**Do:** **Wapas**, then **+ Nayi chat** in the sidebar, switch the language to **हिंदी**,
then speak or type `दो महीने से घुटने में दर्द है`. It asks "जोड़ों या घुटने में दर्द के साथ
क्या इनमें से कुछ है?"; tap **इनमें से कुछ नहीं**.
**Show:** "डॉक्टर से फ़ोन / वीडियो पर बात", the dial on **आज ही**, and a doctor who consults
by video (no department is shown); tap **और 2 देखें** for two more. Tap **सुनाइए** to hear it.
**Say:** "The whole app switches to Hindi and can read the answer aloud. A long-standing
pain with no danger sign goes to a doctor on video today. Doctors in the roster consult by
video, so distance does not count for them."

### 2:00 to 2:25. A question that can change everything
**Do:** **नई चैट** (the Hindi **Nayi chat**), switch back to **Hinglish**, type
`Mere bete ko bukhar hai`.
**Show:** the fever danger check; tap **Inme se kuch nahi**. Then **Bachche ki umar kitni hai?**
Tap **3 mahine se kam**.
**Show:** emergency: a danger sign in a young baby.
**Say:** "It asks only when the answer can change the decision. Fever in a baby under
three months is an emergency, so it asks the age."

### 2:25 to 2:50. For the judges
**Do:** **Wapas** (the red screen covers the sidebar), then open **Kaise kaam karta hai**
in the sidebar.
**Show:** the steps, **93%** right care on new, unseen messages (earlier rules: 74%),
**209/209** caregiver matches, the speed tile, and the last API request and response with
its time ("... ms mein jawab").
**Say:** "This is the exact API call behind the screen, in the problem statement's JSON
schema. Our fine-tuned MuRIL model answers in under 0.1 seconds on the server's CPU; about
2 seconds when Claude gives a second opinion on an unsure case. Emergencies like the last
one are caught by the danger-sign rules, which nothing can override."

### Spare examples (all checked on the live server)
- `dadi ko bedsore dressing chahiye` → home nursing, today, three medics with wound dressing
  (one shown, tap **Aur 2 dekhein** for the rest).
- `Want a CBC and thyroid test with home sample collection` → lab test at home, scheduled,
  three sample collectors (again behind **Aur 2 dekhein**).
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

- **Mic does not hear:** type the same first message; the result is identical. Answers are
  tapped, never spoken.
- **Read-aloud is silent:** no Hindi voice on the laptop. Say so and move on.
- **API down:** restart it with the command above; the web app shows a retry button on
  the failed message. As a last resort set `VITE_USE_MOCKS=1` in `web/.env` and restart
  `npm run dev` (fever, chest pain, knee pain and injection work on sample data).
- **Phone view:** in Chrome DevTools pick a phone size. The sidebar becomes a top bar and
  a bottom tab bar (Jaanch, Bookings, SOS, Jaankari, Settings).

## Likely questions

- **"Where is the AI? Is this rules or RAG?"** Neither. A fine-tuned MuRIL model (Google's
  BERT for Indian languages) routes every request: care type, urgency, the symptoms it
  understood and who the patient is, with a confidence band. There is no retrieval at run
  time. Emergencies are caught by the danger-sign lexicon, the safety net, plus the model's
  own emergency sense when it is very sure; every guardrail that fired is listed under
  "Suraksha jaanch".
- **"What does the model actually decide vs the lexicon?"** The lexicon catches emergencies:
  a named danger sign goes to 112 and nothing can remove it. The model routes everything else:
  care type and urgency. It also calls 112 itself when it is at least 97% sure and the words
  name no everyday symptom. Its red-flag head is weak and not relied on; in the hold-out run
  the model alone caught 65% of emergencies, which is exactly why the lexicon is the detector.
- **"The organisers gave 340 rows. How did you train on so little?"** Those rows hold only 66
  distinct messages. So we used teacher → student distillation: Claude Opus 5.5 wrote 2,743
  new messages for 62 case families whose labels we fixed in a labelling guide, and MuRIL was
  fine-tuned on them. The organisers' 340 rows were never training rows; they are our test set.
- **"Did your training data see the test set?"** Not as training rows. The teacher was given
  the organisers' messages only as a do-not-copy list, and anything within cosine 0.8 of them
  was removed. Close paraphrases can remain, which is why we call the 1.0 on their rows not
  blind and quote the numbers below. (The older TF-IDF fallback, used only without the model
  file, was trained on them.)
- **"Isn't 100% suspicious? Overfitting?"** The organisers' messages are short and clear. Our
  honest numbers: 83% on 12 whole case families the model never saw (the hold-out run, before
  the final training), 0.966 care F1 on the organisers' rows before any error analysis, and
  93.3% on 150 fresh messages on the first run. Training accuracy is 99.6%, so there is a gap on
  brand-new kinds of request; that is what the guardrails and the follow-up questions are for.
- **"Type nonsense: why doesn't it say it did not understand?"** It does now. Show it with
  `चाय ले लो चाय`: after about 2 seconds it answers "माफ़ कीजिए, मैं समझ नहीं पाया। क्या
  तकलीफ़ है...?" with tap options (बुखार, दर्द, डॉक्टर से बात...). Typing in Devanagari
  switches the screen to Hindi, so switch back to **Hinglish** after. (Roman keyboard mash
  such as "asdf qwerty" is read as English and gets an English "Sorry..."; use the Hindi
  example.) A classifier always picks one of its classes, and it is confident even on words it
  never saw. So when the words name nothing medical, Claude gives a second opinion; that is
  the 2-second wait. It asks up to three times, then offers a doctor call. It never books a
  nurse on a guess. The "Suraksha jaanch" list shows this as "Baat samjhi gayi". We tested
  1,345 nonsense, off-topic and mixed chats this way.
- **"Why is the 3.9-star medic first?"** The order is the organisers' own score, from their
  README: 0.35 language + 0.30 distance + 0.20 skill + 0.15 rating. Sunita Chauhan speaks
  Hindi and is 1.3 km away; Naveen Sharma (4.0★) is about 3 km away and Manoj Das (4.1★)
  about 9 km. Being close outweighs a tenth of a star. These weights reproduce all 209 of
  their labelled matches, so we kept them. Free time is shown on the card but not scored, as
  in their labels, and equal scores keep the roster's order.
- **"Why do 'Dadi gir gayi' or swollen feet in pregnancy go straight to 112?"** Safety first,
  on purpose. A fall in an older person can hide a hip fracture or bleeding in the head that
  shows hours later. Most foot swelling in pregnancy is harmless, but it can be the first sign
  of pre-eclampsia. A family cannot tell these apart at home, so both are on our danger-sign
  list, and a danger sign skips the questions. A false alarm costs a phone call; a missed
  emergency can cost a life. The honest cost: "gir gaye the, ab theek hain" also gets 112.
  Asking one check question first (head hit? can they stand?) is our next step.
- **"What if I type 'ok thank you'?"** After a decision the chat starts fresh, so it is read
  as a new message. It names nothing medical, so Claude takes a second look (about 2 s) and
  the app replies "Sorry, I could not understand that. What is the problem...?" with tap
  options. Nothing is booked or escalated. A short polite goodbye is a small fix we have not
  made yet. Do not type it on stage.
- **"The tile says < 0.1 s, the panel says 90 ms?"** The model alone takes about 20-60 ms. The panel times the whole request: rules, model, the next question and caregiver
  matching, mostly 20 to 90 ms on the demo flows (once 111 ms). Either way, about a tenth of a
  second or less; Claude, when asked, adds about 2 s.
- **"New chat, incognito, history?"** In the web app's sidebar chat list (☰ on a phone) and
  the Android app's top row: History (saved on the device only), Incognito (never saved, with
  a banner), and + Nayi chat.
- **"Why not just call an LLM?"** Seconds per answer, health details sent outside, network
  needed during scoring. With MuRIL a whole answer takes under 0.1 s on the server's CPU.
  Claude (about 2 s) is asked only when the model is unsure or the words name nothing our
  lists know. It can add an emergency, and on such words overrule the model's own 112 guess,
  but it is never asked when the lexicon names a danger sign.
- **"What if Claude is down?"** Nothing breaks: an error or the 8 s timeout is ignored, and the
  lexicon and the model answer alone. On words that name nothing medical the model's 112 then
  stands (a false alarm costs less than a miss); an unsure case gets a question in the app,
  and in the API the rules' choice, else the model's. The honest gap: a few emergencies in
  words neither the lexicon nor the model knows are caught only by Claude. It is on for the
  live server.
- **"How did you make the predictions file?"** `python -m scripts.predict_csv` runs the API's
  default path, so it now also writes a `follow_up_question` column: a row whose intent is
  unclear gets a question and no care type, as in the organisers' labels.
- **"What if the organisers' caregiver file looks different?"** Field names are mapped
  loosely (id or caregiver_id, location or lat/lng, lists or comma text); a file that
  cannot be read falls back to the sample profiles and `/health` says why.
- **"Is user data stored?"** No request text is logged or stored. Bookings live in
  server memory and in the browser.

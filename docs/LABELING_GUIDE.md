# Labeling guide

How every training message for the triage model gets its label. The model (MuRIL,
`app/triage/student.py`) is trained on messages written for us by Claude
(`scripts/gen_data.py`); Claude only writes the text. The label of each message is fixed
by the **case family** it was written for, using the rules below.

## Sources

- The organisers' dataset README (`data/sanocare_v1/README.md`): the enums, the nine
  red flags, "any red flag ⇒ `emergency_112`, `emergency`, no caregivers", follow-up when
  the intent is unclear.
- The organisers' 340 labelled rows. They contain 22 situations (66 distinct messages),
  and their labels set the conventions:
  - **Home nursing** is always `same_day`. It covers procedures: injections (IM, insulin),
    wound and post-op dressing, bedsores.
  - **Medic home visit** is always `same_day`. It covers a general complaint needing an
    in-person check: fever with cough, a weak elderly person, BP/sugar checked at home.
  - **Lab test at home** is always `scheduled`.
  - **Teleconsultation** is always `same_day`. It covers mild issues where the person
    wants to consult, report reviews and second opinions.
  - "Doctor chahiye" and "help chahiye" alone are a follow-up.
- Public triage guidance for what counts as a danger sign: the Emergency Severity Index
  (ESI) handbook (AHRQ) and WHO ETAT. Examples are chest pain, severe breathlessness,
  unresponsiveness, uncontrolled bleeding, stroke signs, seizures, fever in a young
  infant, suicidal intent, severe dehydration, poisoning, snake bite, severe burns,
  anaphylaxis and pregnancy bleeding.

## Rules

1. **Any danger sign wins.** The care type is `emergency_112` and the urgency is
   `emergency`. The red flag comes from the organisers' nine (`chest_pain`,
   `breathlessness`, `unconsciousness`, `severe_bleeding`, `stroke_symptoms`, `seizure`,
   `high_fever_infant`, `suicidal_ideation`, `severe_dehydration`). Other emergencies,
   such as poisoning, snake bite, severe burns, anaphylaxis, pregnancy bleeding or a
   head injury with vomiting, get `other_emergency`.
2. A **specific nursing procedure** goes to `home_nursing`, `same_day`.
3. A **test with home sample collection** goes to `lab_test_home`, `scheduled`.
4. A **general complaint needing someone to examine at home** goes to
   `paramedic_home_visit`, `same_day`. This applies to fever (anyone older than one
   year), vomiting or loose motions without dehydration, weakness, dizziness, a minor
   fall, swelling, burning urine, or pain when a home check is asked for.
5. A **mild issue or a wish to talk to a doctor** goes to `teleconsultation`,
   `same_day`. Examples are acidity, a mild cold in a healthy adult, skin and hair
   issues, reports, a second opinion, medicine questions, diabetes or BP follow-up,
   routine pregnancy questions, a child's mild issue, a specialist consult, stress and
   sleep problems.
6. **The intent is unclear** (a greeting, "help", "doctor chahiye" with no need, "tabiyat
   theek nahi" with no symptom): the care type is null and a follow-up question is asked.
7. **Not about health care** (food, cab, phone, cricket): the care type is null. The bot
   says it only helps with home health care (class `out_of_scope`, which the API returns
   as a follow-up question).
8. The model never names a disease or a medicine. Messages never contain medicine names
   or doses.

## Checks on the generated data (`scripts/train_student.py prepare`)

- Exact duplicates are removed.
- Families added after the first model's error analysis (so the final model's scores on the
  organisers' rows are not blind): `T_reports_talk`, `T_mild_self`, `P_fever_self`, `H_negated`,
  `H_minor_injury`, `H_worry`, `H_mood_low`.
- Anything with character-n-gram cosine of 0.80 or more to any of the organisers' 340
  messages is removed. The teacher saw those messages only as a do-not-copy list
  (`scripts/gen_data.py`); the rows are the test set and are never training rows.
- Non-emergency messages in which the red-flag rules find a danger sign are removed. The
  teacher may have slipped one in.
- Roman-script copies are made of 35% of the Hindi messages, and light typos are added
  to 15% of the Roman ones.
- Multi-turn examples are built: a vague first message, then our question, then the
  real need; a complaint, then "kitne din se?", then "2 din se"; a complaint, then the
  danger question, then a danger sign.

## Case families

### Medic home visit (`paramedic_home_visit`), same day

| Family | What the message says | Red flags | Messages |
|---|---|---|---|
| `P_fever_cough` | Fever together with cough or cold for 1 to 5 days. Breathing is fine. Wants help / a check. | - | 42 |
| `P_fever` | Fever (bukhar), alone or with body ache or chills, for a few hours up to about a week. A child here is older than 1 year. No breathing trouble, no fits, no drowsiness. | - | 42 |
| `P_fever_self` | The writer (or another adult) reports FEVER, often short and in first person: 'mujhe bukhar hai', 'bukhar aur khansi hai 2 din se', 'fever since yesterday with body ache', 'kal raat se tez bukhar'. Any fever gets someone to check at home. No danger signs. | - | 60 |
| `P_weak_elderly` | An old parent or grandparent is weak, tired, not eating well or low on energy. Family wants someone to check them at home. Fully conscious, talking normally. | - | 42 |
| `P_bp_sugar_check` | Wants BP and/or blood sugar checked at home once by someone (with a machine/glucometer). Not a lab sample. No symptoms of emergency. | - | 42 |
| `P_vomit_loose` | Vomiting or loose motions for about a day, still drinking water and passing urine, not drowsy. Wants a home check. | - | 42 |
| `P_dizzy` | Mild dizziness or giddiness, for example on standing up. No fainting, no chest pain, no weakness of one side, speech normal. | - | 42 |
| `P_minor_fall` | Slipped or had a small fall at home, some pain or a small bruise, can walk and talk normally, did not hit the head hard, no heavy bleeding. Wants someone to come and check. | - | 37 |
| `P_cold_elderly` | Old person with cold, sore throat or cough for a few days; family wants a home check-up. Breathing normal. | - | 41 |
| `P_swelling` | Swelling in feet or legs for some days. No breathlessness, no chest pain. | - | 42 |
| `P_urine` | Burning or frequent urination, mild lower belly discomfort. No fever above normal worries, no blood. Wants someone to examine at home. | - | 42 |
| `P_pain_home` | Back pain, knee or joint pain, or mild stomach ache (not severe), and the person explicitly wants someone to come home and check. | - | 41 |
| `P_home_checkup` | Says the patient is unwell (one mild complaint like tiredness, loss of appetite, mild fever feeling) and explicitly asks for a check-up at home. | - | 41 |
| `H_negated` | A real but non-urgent complaint (fever, weakness, dizziness on standing, cough, vomiting once) where the writer explicitly DENIES danger signs: 'saans ki dikkat nahi', 'behosh nahi hue, bas chakkar aaya', 'seene mein dard nahi', 'hosh mein hain, baat kar rahe hain', 'not unconscious, just tired'. Every danger word must be clearly negated. | - | 53 |
| `H_minor_injury` | A small fall or bump that is already fine: fell from the sofa or bed and is now playing, small scratch or bruise, a tiny cut that bled a little and stopped, did not hit the head hard, no vomiting, fully alert. Family wants someone to have a look. | - | 54 |

### Home nursing (`home_nursing`), same day

| Family | What the message says | Red flags | Messages |
|---|---|---|---|
| `N_im_injection` | Doctor has prescribed an injection (IM injection, a course of injections) and they need someone to give it at home. Never name the medicine. | - | 41 |
| `N_insulin` | Needs help with insulin injections at home (elderly cannot do it, family member unsure). | - | 42 |
| `N_iv_drip` | Doctor advised an IV drip / saline / IV course at home; needs someone to set it up. | - | 42 |
| `N_postop_dressing` | Wound or stitches dressing after an operation; dressing change at home. Wound is healing, no heavy bleeding. | - | 42 |
| `N_bedsore` | Bedridden elderly person has a bedsore/pressure sore that needs dressing and care. | - | 38 |
| `N_catheter` | Urinary catheter needs to be changed or put in at home. | - | 42 |
| `N_wound_minor` | A small cut, scrape or minor burn that has already stopped bleeding needs cleaning and dressing at home (bandage, patti badalni hai). | - | 38 |
| `N_stitch_removal` | Stitches or staples need to be removed at home after surgery. | - | 42 |
| `N_bedridden_care` | Bedridden or post-stroke (old, stable) patient needs nursing care at home: sponge bath, feeding tube care, position change, regular nursing visits. | - | 30 |
| `N_nebulization` | Doctor advised nebulization at home and they need someone to do it. Breathing is currently comfortable. | - | 42 |

### Lab test at home (`lab_test_home`), scheduled

| Family | What the message says | Red flags | Messages |
|---|---|---|---|
| `L_blood_tests` | Wants specific blood tests (CBC, thyroid, lipid profile, HbA1c, vitamin D, B12, liver or kidney function) with home sample collection. | - | 42 |
| `L_sugar_fasting` | Fasting or PP blood sugar test, sample to be collected at home (often tomorrow morning). | - | 41 |
| `L_full_body` | Full body check-up / health package with home collection. | - | 42 |
| `L_urine_stool` | Urine or stool test, sample pickup from home. | - | 42 |
| `L_doctor_asked` | Doctor has written some tests on the prescription; wants to book them with home sample collection. | - | 41 |

### Doctor teleconsultation (`teleconsultation`), same day

| Family | What the message says | Red flags | Messages |
|---|---|---|---|
| `T_acidity` | Mild acidity, gas, indigestion or bloating; wants to consult a doctor online / on call. | - | 42 |
| `T_reports` | Has test reports and wants a doctor to explain or review them. | - | 42 |
| `T_second_opinion` | Wants a second opinion on a prescription, treatment plan or advice given by a doctor. | - | 42 |
| `T_mild_cold` | Mild cold, sneezing or sore throat in a healthy adult who wants to talk to a doctor online (no home visit asked). | - | 42 |
| `T_skin` | Mild skin issue: itching, small rash, pimples/acne, hair fall, dandruff; wants doctor advice. | - | 42 |
| `T_mind` | Stress, anxiety, low mood or poor sleep and wants to talk to a doctor or counsellor. No thoughts of self-harm. | - | 42 |
| `T_medicine_query` | A question about medicines already prescribed (timing, missed dose, side effect worry, food). Do not name medicines. | - | 41 |
| `T_chronic` | Diabetes or BP follow-up advice: readings a bit high, diet or lifestyle question, wants to talk to a doctor. No emergency symptoms. | - | 42 |
| `T_pregnancy_query` | Routine pregnancy question (diet, mild nausea, which tests, sleep) for a doctor. No bleeding, no severe pain, baby movements normal. | - | 42 |
| `T_child_query` | Parent wants online doctor advice for a child's mild issue (mild cold, teething, diet, constipation). Child is playful and active. | - | 42 |
| `T_specialist` | Wants to consult a specific specialist online (dermatologist, gynaecologist, cardiologist for a follow-up, orthopaedic, ENT) for a non-urgent issue. | - | 42 |
| `T_headache_mild` | Mild or usual headache, migraine pattern they know, wants doctor advice online. Not the worst headache ever, no weakness, speech normal. | - | 42 |
| `T_mild_self` | A mild, self-limiting complaint WITHOUT any fever that the person is coping with at home and does NOT ask for a home visit: acidity, gas or heartburn (often eased by an antacid), mild cold or sneezing, a mild cough, a sore throat, an old knee or back ache that flares up, a toothache, a small rash, mild tiredness after a long day. Healthy adult or the writer's parent, eating and sleeping fine. Never mention fever. | - | 114 |
| `T_reports_talk` | Wants to talk to / discuss with / show a doctor their test reports, scan, X-ray or lab results (always mention the reports or results), e.g. 'want to talk to a doctor about my reports'. | - | 42 |
| `H_worry` | Worry or fear about something serious without any present sign: 'darr hai stroke na ho jaye par sab theek hai', 'heart ka darr hai, abhi koi dard nahi', 'pehle ek baar behosh hue the saal bhar pehle, ab theek hain'. Wants advice from a doctor. | - | 54 |
| `H_mood_low` | Feeling low, stressed, tired, sleeping badly or anxious, explicitly with no thoughts of self-harm (may say 'aisa kuch nahi sochta', 'no thoughts of hurting myself'). Wants to talk to a doctor or counsellor. | - | 54 |

### Emergency (`emergency_112`), emergency

| Family | What the message says | Red flags | Messages |
|---|---|---|---|
| `E_chest_pain` | Chest pain, pressure or heaviness, possibly spreading to arm/jaw, sweating. | chest_pain | 42 |
| `E_chest_breath` | Severe chest pain together with difficulty breathing. | chest_pain, breathlessness | 42 |
| `E_breathless` | Severe difficulty breathing, gasping, lips turning blue, cannot speak full sentences. | breathlessness | 41 |
| `E_unconscious` | Collapsed, fainted and not waking up, not responding, unconscious. | unconsciousness | 42 |
| `E_bleeding` | Heavy bleeding that will not stop (accident, deep cut, vomiting blood). | severe_bleeding | 42 |
| `E_stroke` | Sudden face drooping, slurred speech, weakness or numbness on one side, sudden confusion. | stroke_symptoms | 42 |
| `E_seizure` | Fits, convulsions, body shaking and stiff, eyes rolled up, frothing. | seizure | 42 |
| `E_infant_fever` | A baby under 3 months with fever, or a baby under 1 year with very high fever (103-104 F) who is very drowsy, not feeding, or crying non-stop. | high_fever_infant | 42 |
| `E_suicidal` | Wants to die, thinking of ending life, has a plan, says goodbye to family, or a family member says someone is talking about killing themselves. Write it respectfully. | suicidal_ideation | 42 |
| `E_dehydration` | Severe dehydration: many loose motions/vomiting, not passing urine, very drowsy, sunken eyes, cannot keep water down. | severe_dehydration | 42 |
| `E_other` | Other emergencies: poisoning or swallowed chemicals, snake bite, severe burns, face and throat swelling after allergy, pregnancy with heavy bleeding or severe pain or water broke early, head injury with vomiting or confusion, choking, electric shock. | other_emergency | 41 |

### Follow-up question (`care_type` null)

| Family | What the message says | Red flags | Messages |
|---|---|---|---|
| `F_greeting` | Only a greeting or checking if someone is there (hello, namaste, koi hai). | - | 42 |
| `F_help` | Asks for help in general without saying what the problem or service is. | - | 42 |
| `F_doctor_vague` | Says they need a doctor / nurse / someone, or want to book something for a family member, but gives no symptom, test or procedure. | - | 42 |
| `F_unwell_vague` | Says someone is not well / tabiyat theek nahi but names no symptom at all. | - | 41 |
| `O_non_health` | Requests that have nothing to do with health care: food order, cab, phone repair, weather, cricket score, jokes, homework, jobs. | - | 42 |

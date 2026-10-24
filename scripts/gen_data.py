"""Generate the training set for the triage model (teacher -> student).

The organisers' file has 340 rows but only 65 distinct messages (22 situations x 3
languages), so a model trained on it memorises sentences. Here Claude (the teacher)
writes many new, varied messages for each case family; the LABEL of every family is
fixed by us in FAMILIES below (docs/LABELING_GUIDE.md explains the rules), so the
teacher only writes text and never decides care type, urgency or red flags.

The organisers' 340 rows are never used for training: they are the test set.

    python -m scripts.gen_data                 # all families -> data/generated/raw/*.jsonl
    python -m scripts.gen_data --only E_       # families whose id starts with E_
    python -m scripts.gen_data --rounds 2      # a second, differently styled round

Needs ANTHROPIC_API_KEY (read from the environment or a local .env). Model and use are
declared in the write-up: Claude Opus 5.5, synthetic training text only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "generated" / "raw"
MODEL = "claude-opus-5-5"

WHO = ["self", "adult", "elderly", "child", "infant", "pregnant", "unknown"]
# Tags for the intake (Module 1) "structured symptoms" head: the lexicon's symptom and
# service ids, plus a few emergency findings.
TAGS = [
    "fever", "cough", "cold", "sore_throat", "headache", "body_ache", "vomiting", "diarrhoea",
    "stomach_pain", "heartburn", "back_pain", "joint_pain", "skin", "weakness", "dizziness",
    "jaundice", "urinary", "eye", "ear", "tooth", "wound", "injury", "blood_pressure",
    "blood_sugar", "palpitations", "sweating", "mental_health", "constipation", "swelling",
    "minor_burn", "animal_bite", "pain",
    "injection", "iv_drip", "dressing", "catheter", "bedsore", "elderly_care", "post_op",
    "vaccination", "sample_collection", "vitals_check", "checkup", "teleconsult", "report_review",
    "chest_pain", "breathlessness", "unconscious", "bleeding", "stroke_signs", "seizure",
    "suicidal", "dehydration", "pregnancy", "poisoning", "burn", "allergy", "head_injury",
]

# id, care, urgency, red_flags (organisers' vocabulary or "other_emergency"),
# allowed "who", description for the teacher.
FAMILIES: list[tuple[str, str | None, str | None, list[str], list[str], str]] = [
    # ---- Medic home visit (paramedic_home_visit), same day: a general complaint that needs
    # someone to come and assess in person. No danger signs.
    ("P_fever_cough", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly"],
     "Fever together with cough or cold for 1 to 5 days. Breathing is fine. Wants help / a check."),
    ("P_fever", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly", "child"],
     "Fever (bukhar), alone or with body ache or chills, for a few hours up to about a week. "
     "A child here is older than 1 year. No breathing trouble, no fits, no drowsiness."),
    ("P_fever_self", "paramedic_home_visit", "same_day", [], ["self", "adult"],
     "The writer (or another adult) reports FEVER, often short and in first person: 'mujhe "
     "bukhar hai', 'bukhar aur khansi hai 2 din se', 'fever since yesterday with body ache', "
     "'kal raat se tez bukhar'. Any fever gets someone to check at home. No danger signs."),
    ("P_weak_elderly", "paramedic_home_visit", "same_day", [], ["elderly"],
     "An old parent or grandparent is weak, tired, not eating well or low on energy. Family "
     "wants someone to check them at home. Fully conscious, talking normally."),
    ("P_bp_sugar_check", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly"],
     "Wants BP and/or blood sugar checked at home once by someone (with a machine/glucometer). "
     "Not a lab sample. No symptoms of emergency."),
    ("P_vomit_loose", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly", "child"],
     "Vomiting or loose motions for about a day, still drinking water and passing urine, "
     "not drowsy. Wants a home check."),
    ("P_dizzy", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly"],
     "Mild dizziness or giddiness, for example on standing up. No fainting, no chest pain, "
     "no weakness of one side, speech normal."),
    ("P_minor_fall", "paramedic_home_visit", "same_day", [], ["elderly", "adult"],
     "Slipped or had a small fall at home, some pain or a small bruise, can walk and talk "
     "normally, did not hit the head hard, no heavy bleeding. Wants someone to come and check."),
    ("P_cold_elderly", "paramedic_home_visit", "same_day", [], ["elderly"],
     "Old person with cold, sore throat or cough for a few days; family wants a home check-up. "
     "Breathing normal."),
    ("P_swelling", "paramedic_home_visit", "same_day", [], ["elderly", "adult"],
     "Swelling in feet or legs for some days. No breathlessness, no chest pain."),
    ("P_urine", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly"],
     "Burning or frequent urination, mild lower belly discomfort. No fever above normal "
     "worries, no blood. Wants someone to examine at home."),
    ("P_pain_home", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly"],
     "Back pain, knee or joint pain, or mild stomach ache (not severe), and the person "
     "explicitly wants someone to come home and check."),
    ("P_home_checkup", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly"],
     "Says the patient is unwell (one mild complaint like tiredness, loss of appetite, "
     "mild fever feeling) and explicitly asks for a check-up at home."),

    # ---- Home nursing (home_nursing), same day: a specific nursing procedure.
    ("N_im_injection", "home_nursing", "same_day", [], ["self", "adult", "elderly", "child"],
     "Doctor has prescribed an injection (IM injection, a course of injections) and they need "
     "someone to give it at home. Never name the medicine."),
    ("N_insulin", "home_nursing", "same_day", [], ["elderly", "adult"],
     "Needs help with insulin injections at home (elderly cannot do it, family member unsure)."),
    ("N_iv_drip", "home_nursing", "same_day", [], ["self", "adult", "elderly"],
     "Doctor advised an IV drip / saline / IV course at home; needs someone to set it up."),
    ("N_postop_dressing", "home_nursing", "same_day", [], ["self", "adult", "elderly"],
     "Wound or stitches dressing after an operation; dressing change at home. Wound is healing, "
     "no heavy bleeding."),
    ("N_bedsore", "home_nursing", "same_day", [], ["elderly"],
     "Bedridden elderly person has a bedsore/pressure sore that needs dressing and care."),
    ("N_catheter", "home_nursing", "same_day", [], ["elderly", "adult"],
     "Urinary catheter needs to be changed or put in at home."),
    ("N_wound_minor", "home_nursing", "same_day", [], ["self", "adult", "elderly", "child"],
     "A small cut, scrape or minor burn that has already stopped bleeding needs cleaning and "
     "dressing at home (bandage, patti badalni hai)."),
    ("N_stitch_removal", "home_nursing", "same_day", [], ["self", "adult", "elderly"],
     "Stitches or staples need to be removed at home after surgery."),
    ("N_bedridden_care", "home_nursing", "same_day", [], ["elderly"],
     "Bedridden or post-stroke (old, stable) patient needs nursing care at home: sponge bath, "
     "feeding tube care, position change, regular nursing visits."),
    ("N_nebulization", "home_nursing", "same_day", [], ["elderly", "child", "adult"],
     "Doctor advised nebulization at home and they need someone to do it. Breathing is "
     "currently comfortable."),

    # ---- Lab test at home (lab_test_home), scheduled.
    ("L_blood_tests", "lab_test_home", "scheduled", [], ["self", "adult", "elderly"],
     "Wants specific blood tests (CBC, thyroid, lipid profile, HbA1c, vitamin D, B12, liver or "
     "kidney function) with home sample collection."),
    ("L_sugar_fasting", "lab_test_home", "scheduled", [], ["self", "adult", "elderly"],
     "Fasting or PP blood sugar test, sample to be collected at home (often tomorrow morning)."),
    ("L_full_body", "lab_test_home", "scheduled", [], ["self", "adult", "elderly"],
     "Full body check-up / health package with home collection."),
    ("L_urine_stool", "lab_test_home", "scheduled", [], ["self", "adult", "elderly", "child"],
     "Urine or stool test, sample pickup from home."),
    ("L_doctor_asked", "lab_test_home", "scheduled", [], ["self", "adult", "elderly"],
     "Doctor has written some tests on the prescription; wants to book them with home sample "
     "collection."),

    # ---- Teleconsultation (virtual doctor), same day.
    ("T_acidity", "teleconsultation", "same_day", [], ["self", "adult"],
     "Mild acidity, gas, indigestion or bloating; wants to consult a doctor online / on call."),
    ("T_reports", "teleconsultation", "same_day", [], ["self", "adult", "elderly"],
     "Has test reports and wants a doctor to explain or review them."),
    ("T_second_opinion", "teleconsultation", "same_day", [], ["self", "adult", "elderly", "child"],
     "Wants a second opinion on a prescription, treatment plan or advice given by a doctor."),
    ("T_mild_cold", "teleconsultation", "same_day", [], ["self", "adult"],
     "Mild cold, sneezing or sore throat in a healthy adult who wants to talk to a doctor "
     "online (no home visit asked)."),
    ("T_skin", "teleconsultation", "same_day", [], ["self", "adult", "child"],
     "Mild skin issue: itching, small rash, pimples/acne, hair fall, dandruff; wants doctor advice."),
    ("T_mind", "teleconsultation", "same_day", [], ["self", "adult"],
     "Stress, anxiety, low mood or poor sleep and wants to talk to a doctor or counsellor. "
     "No thoughts of self-harm."),
    ("T_medicine_query", "teleconsultation", "same_day", [], ["self", "adult", "elderly"],
     "A question about medicines already prescribed (timing, missed dose, side effect worry, "
     "food). Do not name medicines."),
    ("T_chronic", "teleconsultation", "same_day", [], ["self", "adult", "elderly"],
     "Diabetes or BP follow-up advice: readings a bit high, diet or lifestyle question, wants "
     "to talk to a doctor. No emergency symptoms."),
    ("T_pregnancy_query", "teleconsultation", "same_day", [], ["pregnant"],
     "Routine pregnancy question (diet, mild nausea, which tests, sleep) for a doctor. No "
     "bleeding, no severe pain, baby movements normal."),
    ("T_child_query", "teleconsultation", "same_day", [], ["child"],
     "Parent wants online doctor advice for a child's mild issue (mild cold, teething, diet, "
     "constipation). Child is playful and active."),
    ("T_specialist", "teleconsultation", "same_day", [], ["self", "adult", "elderly"],
     "Wants to consult a specific specialist online (dermatologist, gynaecologist, cardiologist "
     "for a follow-up, orthopaedic, ENT) for a non-urgent issue."),
    ("T_headache_mild", "teleconsultation", "same_day", [], ["self", "adult"],
     "Mild or usual headache, migraine pattern they know, wants doctor advice online. Not the "
     "worst headache ever, no weakness, speech normal."),

    ("T_mild_self", "teleconsultation", "same_day", [], ["self", "adult"],
     "A mild, self-limiting complaint WITHOUT any fever that the person is coping with at home "
     "and does NOT ask for a home visit: acidity, gas or heartburn (often eased by an antacid), "
     "mild cold or sneezing, a mild cough, a sore throat, an old knee or back ache that flares "
     "up, a toothache, a small rash, mild tiredness after a long day. Healthy adult or the "
     "writer's parent, eating and sleeping fine. Never mention fever."),
    ("T_reports_talk", "teleconsultation", "same_day", [], ["self", "adult", "elderly"],
     "Wants to talk to / discuss with / show a doctor their test reports, scan, X-ray or lab "
     "results (always mention the reports or results), e.g. 'want to talk to a doctor about my "
     "reports'."),

    # ---- Hard negatives: danger words that are denied, past, or only feared. NOT emergencies.
    ("H_negated", "paramedic_home_visit", "same_day", [], ["self", "adult", "elderly"],
     "A real but non-urgent complaint (fever, weakness, dizziness on standing, cough, vomiting once) "
     "where the writer explicitly DENIES danger signs: 'saans ki dikkat nahi', 'behosh nahi hue, "
     "bas chakkar aaya', 'seene mein dard nahi', 'hosh mein hain, baat kar rahe hain', 'not "
     "unconscious, just tired'. Every danger word must be clearly negated."),
    ("H_minor_injury", "paramedic_home_visit", "same_day", [], ["child", "adult", "elderly"],
     "A small fall or bump that is already fine: fell from the sofa or bed and is now playing, "
     "small scratch or bruise, a tiny cut that bled a little and stopped, did not hit the head "
     "hard, no vomiting, fully alert. Family wants someone to have a look."),
    ("H_worry", "teleconsultation", "same_day", [], ["self", "adult", "elderly"],
     "Worry or fear about something serious without any present sign: 'darr hai stroke na ho "
     "jaye par sab theek hai', 'heart ka darr hai, abhi koi dard nahi', 'pehle ek baar behosh hue "
     "the saal bhar pehle, ab theek hain'. Wants advice from a doctor."),
    ("H_mood_low", "teleconsultation", "same_day", [], ["self", "adult"],
     "Feeling low, stressed, tired, sleeping badly or anxious, explicitly with no thoughts of "
     "self-harm (may say 'aisa kuch nahi sochta', 'no thoughts of hurting myself'). Wants to talk "
     "to a doctor or counsellor."),

    # ---- Emergency (emergency_112): red flags.
    ("E_chest_pain", "emergency_112", "emergency", ["chest_pain"], ["self", "adult", "elderly"],
     "Chest pain, pressure or heaviness, possibly spreading to arm/jaw, sweating."),
    ("E_chest_breath", "emergency_112", "emergency", ["chest_pain", "breathlessness"],
     ["self", "adult", "elderly"], "Severe chest pain together with difficulty breathing."),
    ("E_breathless", "emergency_112", "emergency", ["breathlessness"],
     ["self", "adult", "elderly", "child", "pregnant"],
     "Severe difficulty breathing, gasping, lips turning blue, cannot speak full sentences."),
    ("E_unconscious", "emergency_112", "emergency", ["unconsciousness"],
     ["adult", "elderly", "child", "unknown"],
     "Collapsed, fainted and not waking up, not responding, unconscious."),
    ("E_bleeding", "emergency_112", "emergency", ["severe_bleeding"],
     ["self", "adult", "elderly", "child", "unknown"],
     "Heavy bleeding that will not stop (accident, deep cut, vomiting blood)."),
    ("E_stroke", "emergency_112", "emergency", ["stroke_symptoms"], ["adult", "elderly"],
     "Sudden face drooping, slurred speech, weakness or numbness on one side, sudden confusion."),
    ("E_seizure", "emergency_112", "emergency", ["seizure"], ["adult", "elderly", "child"],
     "Fits, convulsions, body shaking and stiff, eyes rolled up, frothing."),
    ("E_infant_fever", "emergency_112", "emergency", ["high_fever_infant"], ["infant"],
     "A baby under 3 months with fever, or a baby under 1 year with very high fever (103-104 F) "
     "who is very drowsy, not feeding, or crying non-stop."),
    ("E_suicidal", "emergency_112", "emergency", ["suicidal_ideation"], ["self", "adult"],
     "Wants to die, thinking of ending life, has a plan, says goodbye to family, or a family "
     "member says someone is talking about killing themselves. Write it respectfully."),
    ("E_dehydration", "emergency_112", "emergency", ["severe_dehydration"],
     ["adult", "elderly", "child"],
     "Severe dehydration: many loose motions/vomiting, not passing urine, very drowsy, sunken "
     "eyes, cannot keep water down."),
    ("E_other", "emergency_112", "emergency", ["other_emergency"],
     ["self", "adult", "elderly", "child", "pregnant", "unknown"],
     "Other emergencies: poisoning or swallowed chemicals, snake bite, severe burns, face and "
     "throat swelling after allergy, pregnancy with heavy bleeding or severe pain or water broke "
     "early, head injury with vomiting or confusion, choking, electric shock."),

    # ---- Follow-up needed (care_type null): the intent is not clear yet.
    ("F_greeting", None, None, [], ["unknown"],
     "Only a greeting or checking if someone is there (hello, namaste, koi hai)."),
    ("F_help", None, None, [], ["unknown", "self"],
     "Asks for help in general without saying what the problem or service is."),
    ("F_doctor_vague", None, None, [], ["unknown", "self", "adult", "elderly"],
     "Says they need a doctor / nurse / someone, or want to book something for a family member, "
     "but gives no symptom, test or procedure."),
    ("F_unwell_vague", None, None, [], ["self", "adult", "elderly"],
     "Says someone is not well / tabiyat theek nahi but names no symptom at all."),

    # ---- Out of scope (also care_type null; the bot says it only helps with home care).
    ("O_non_health", None, None, [], ["unknown"],
     "Requests that have nothing to do with health care: food order, cab, phone repair, "
     "weather, cricket score, jokes, homework, jobs."),
]

STYLE_ROUNDS = [
    "Mix the styles: short WhatsApp messages (3-10 words), normal sentences, and a few longer "
    "messages (25-50 words) with extra details (who, since when, what they tried). Include "
    "common typos and missing punctuation in some.",
    "This round: write like a worried family member typing fast or using voice typing: no "
    "punctuation, repeated words, mixed English words inside Hindi (in Devanagari for Hindi "
    "items), polite forms (ji, please, bhaiya), and some messages that mention two people or "
    "add unrelated context before the real need.",
]

SYSTEM = """You write realistic synthetic messages for training a home-healthcare triage model in India (Delhi NCR). Families message the service on WhatsApp in Hinglish (Hindi in Roman letters), Hindi (Devanagari script) or English.

You are given ONE case family with its fixed label. Write messages that clearly belong to that family and would get exactly that label. Rules:
- Vary everything: who the patient is (within the allowed list), relation words (papa, mummy, dadi, nani, bhai, wife, beta, beti, padosi), age when given, duration, wording, length, politeness, word order.
- Hinglish items: Hindi in Roman script with common spellings (bukhar/bukhaar, khansi/khaansi, saans, ulti), English words mixed in.
- Hindi items: Devanagari script; English medical words may appear in Devanagari (इंजेक्शन, रिपोर्ट) or in Roman.
- English items: Indian English.
- Never name diseases as a diagnosis and never name medicines or doses.
- For non-emergency families, do NOT add any danger sign (no chest pain, breathing trouble, unconsciousness, heavy bleeding, fits, one-side weakness, suicidal talk, severe dehydration, infant fever).
- Do not copy or lightly edit these organiser examples: {forbidden}
- For each item also give: who (one of the allowed values), tags (the symptoms/services actually mentioned, from the allowed tag list only), duration_days (number if a duration is stated, else null)."""


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def organiser_texts() -> list[str]:
    p = ROOT / "data" / "sanocare_v1" / "triage_dataset.jsonl"
    seen = []
    for line in p.read_text(encoding="utf-8").splitlines():
        t = json.loads(line)["request"]["user_input"]
        if t not in seen:
            seen.append(t)
    return seen


def schema(allowed_who: list[str]) -> dict:
    item = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "language": {"type": "string", "enum": ["hinglish", "hi", "en"]},
            "who": {"type": "string", "enum": allowed_who},
            "tags": {"type": "array", "items": {"type": "string", "enum": TAGS}},
            "duration_days": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        },
        "required": ["text", "language", "who", "tags", "duration_days"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item}},
        "required": ["items"],
        "additionalProperties": False,
    }


async def one(client, fam, round_i: int, per_lang: int, forbidden: str, sem) -> list[dict]:
    fid, care, urgency, flags, who, desc = fam
    label = (f"care_type={care}, urgency={urgency}, red_flags={flags or []}" if care
             else "care_type=null (the assistant must ask a follow-up question)")
    user = (f"Case family: {fid}\nLabel: {label}\nDescription: {desc}\nAllowed who: {who}\n"
            f"Allowed tags: {TAGS}\n\nWrite {per_lang} Hinglish, {per_lang} Hindi (Devanagari) and "
            f"{per_lang} English messages ({3 * per_lang} items). {STYLE_ROUNDS[round_i % len(STYLE_ROUNDS)]}")
    async with sem:
        for attempt in range(3):
            try:
                r = await client.messages.create(
                    model=MODEL,
                    max_tokens=16000,
                    system=SYSTEM.format(forbidden=forbidden),
                    output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema(who)}},
                    messages=[{"role": "user", "content": user}],
                )
                if r.stop_reason == "refusal":
                    print(f"  {fid} r{round_i}: refused ({getattr(r.stop_details, 'category', None)})")
                    return []
                text = next(b.text for b in r.content if b.type == "text")
                items = json.loads(text)["items"]
                out = []
                for it in items:
                    out.append({"text": it["text"].strip(), "language": it["language"], "who": it["who"],
                                "tags": sorted(set(it["tags"])), "duration_days": it["duration_days"],
                                "family": fid, "care_type": care, "urgency": urgency,
                                "red_flags": flags, "round": round_i})
                print(f"  {fid} r{round_i}: {len(out)} items "
                      f"(in {r.usage.input_tokens}, out {r.usage.output_tokens})")
                return out
            except Exception as e:  # network or parse trouble: retry a couple of times
                print(f"  {fid} r{round_i}: attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:120]}")
                await asyncio.sleep(3 + 5 * attempt)
    return []


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--per-lang", type=int, default=7)
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()
    load_env()
    import anthropic

    client = anthropic.AsyncAnthropic(max_retries=4)
    forbidden = " | ".join(organiser_texts())
    fams = [f for f in FAMILIES if f[0].startswith(args.only)]
    OUT.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    jobs = [one(client, f, r, args.per_lang, forbidden, sem) for r in range(args.rounds) for f in fams]
    results = await asyncio.gather(*jobs)
    by_fam: dict[str, list[dict]] = {}
    for items in results:
        for it in items:
            by_fam.setdefault(it["family"], []).append(it)
    total = 0
    for fid, items in by_fam.items():
        path = OUT / f"{fid}.jsonl"
        old = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() and args.only else []
        keep = old + items
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in keep), encoding="utf-8")
        total += len(items)
    print(f"done: {total} new items in {len(by_fam)} families -> {OUT}")


if __name__ == "__main__":
    random.seed(7)
    asyncio.run(main())

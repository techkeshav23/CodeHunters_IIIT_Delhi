"""Plain-language strings: care and urgency labels, reasoning, emergency help.

Templates only use symptom labels and computed facts, never disease or
medicine names (the clinical-scope rule). `scrub` is a last guard for any
free text that reaches the user.
"""
from __future__ import annotations

import re

from ..config import EMERGENCY_NUMBERS, FLAG_HELPLINES
from ..nlp.extract import Extraction

LANGS = ("en", "hinglish", "hi")

CARE_LABELS = {
    "paramedic": {"en": "Paramedic home visit", "hinglish": "Paramedic ghar aakar check karenge", "hi": "पैरामेडिक घर आकर जाँच करेंगे"},
    "nurse": {"en": "Home nursing", "hinglish": "Ghar pe nursing (nurse aayengi)", "hi": "घर पर नर्सिंग (नर्स आएँगी)"},
    "lab": {"en": "Lab test at home", "hinglish": "Ghar se sample lekar lab test", "hi": "घर से सैंपल लेकर लैब टेस्ट"},
    "gp": {"en": "Talk to a doctor (teleconsultation)", "hinglish": "Doctor se phone / video par baat", "hi": "डॉक्टर से फ़ोन / वीडियो पर बात"},
    "specialist": {"en": "Specialist doctor (teleconsultation)", "hinglish": "Specialist doctor se baat", "hi": "विशेषज्ञ डॉक्टर से बात"},
    "emergency": {"en": "Emergency: call for help now", "hinglish": "Emergency: abhi madad bulayein", "hi": "इमरजेंसी: अभी मदद बुलाएँ"},
}
URGENCY_LABELS = {
    "routine": {"en": "Scheduled", "hinglish": "Time fix karke", "hi": "समय तय करके"},
    "same_day": {"en": "Today", "hinglish": "Aaj hi", "hi": "आज ही"},
    "immediate": {"en": "Now", "hinglish": "Abhi", "hi": "अभी"},
}
SPECIALTY = {
    "ent": "ear, nose and throat", "neurology": "neurology", "gastroenterology": "stomach",
    "orthopaedics": "bone and joint", "dermatology": "skin", "urology": "urinary",
    "ophthalmology": "eye", "dental": "dental", "cardiology": "heart", "psychiatry": "mental health",
}
CARE_PHRASE = {
    "en": {
        ("paramedic", "same_day"): "a same-day paramedic home visit fits",
        ("paramedic", "routine"): "a paramedic home visit in the next few days fits",
        ("nurse", "same_day"): "a nurse home visit today fits",
        ("nurse", "routine"): "a nurse home visit at a convenient time fits",
        ("gp", "same_day"): "a doctor teleconsult today fits",
        ("gp", "routine"): "a doctor teleconsult in the next few days fits",
        ("specialist", "same_day"): "a specialist consult today fits",
        ("specialist", "routine"): "a specialist consult in the next few days fits",
        ("lab", "routine"): "a scheduled home sample collection fits",
        ("lab", "same_day"): "a home sample collection today fits",
    },
    "hinglish": {
        ("paramedic", "same_day"): "Aaj ek paramedic ghar aakar check karenge.",
        ("paramedic", "routine"): "Agle kuch dinon mein ek paramedic ghar aakar check karenge.",
        ("nurse", "same_day"): "Aaj ek nurse ghar aayengi.",
        ("nurse", "routine"): "Aapke time par ek nurse ghar aayengi.",
        ("gp", "same_day"): "Aaj hi doctor se phone / video par baat karein.",
        ("gp", "routine"): "Agle kuch dinon mein doctor se phone / video par baat karein.",
        ("specialist", "same_day"): "Aaj hi specialist doctor se milein.",
        ("specialist", "routine"): "Agle kuch dinon mein specialist doctor se milein.",
        ("lab", "routine"): "Time fix karke ghar se sample liya jayega.",
        ("lab", "same_day"): "Aaj ghar se sample liya jayega.",
    },
    "hi": {
        ("paramedic", "same_day"): "आज एक पैरामेडिक घर आकर जाँच करेंगे।",
        ("paramedic", "routine"): "अगले कुछ दिनों में एक पैरामेडिक घर आकर जाँच करेंगे।",
        ("nurse", "same_day"): "आज एक नर्स घर आएँगी।",
        ("nurse", "routine"): "आपके समय पर एक नर्स घर आएँगी।",
        ("gp", "same_day"): "आज ही डॉक्टर से फ़ोन / वीडियो पर बात करें।",
        ("gp", "routine"): "अगले कुछ दिनों में डॉक्टर से फ़ोन / वीडियो पर बात करें।",
        ("specialist", "same_day"): "आज ही विशेषज्ञ डॉक्टर से मिलें।",
        ("specialist", "routine"): "अगले कुछ दिनों में विशेषज्ञ डॉक्टर से मिलें।",
        ("lab", "routine"): "समय तय करके घर से सैंपल लिया जाएगा।",
        ("lab", "same_day"): "आज घर से सैंपल लिया जाएगा।",
    },
}
EMERGENCY_TITLE = {"en": "This may be an emergency", "hinglish": "Yeh emergency ho sakti hai", "hi": "यह इमरजेंसी हो सकती है"}
EMERGENCY_STEPS = {
    "en": ["Call 112 now.", "Stay with the patient.", "Keep your phone on and share your location."],
    "hinglish": ["Abhi 112 par call karein.", "Mareez ke saath rahein.", "Phone chalu rakhein aur location share karein."],
    "hi": ["अभी 112 पर कॉल करें।", "मरीज़ के साथ रहें।", "फ़ोन चालू रखें और लोकेशन शेयर करें।"],
}
BREATHING_NOTE = {
    "not_reported": {"en": "no breathing difficulty reported", "hinglish": "saans ki dikkat nahi batayi", "hi": "सांस की दिक्कत नहीं बताई"},
    "absent": {"en": "no breathing difficulty", "hinglish": "saans ki dikkat nahi hai", "hi": "सांस की दिक्कत नहीं है"},
}
NO_FLAGS_NOTE = {"en": "no danger signs reported", "hinglish": "koi khatre ka lakshan nahi bataya", "hi": "कोई ख़तरे का लक्षण नहीं बताया"}
AND = {"en": " and ", "hinglish": " aur ", "hi": " और "}


def lang_of(language: str) -> str:
    return language if language in LANGS else "en"


def duration_label(days: float | None, language: str) -> str | None:
    if days is None:
        return None
    lang = lang_of(language)
    if days < 1:
        return {"en": "today", "hinglish": "aaj se", "hi": "आज से"}[lang]
    if days < 7:
        d = int(round(days))
        return {"en": f"{d} day{'s' if d != 1 else ''}", "hinglish": f"{d} din", "hi": f"{d} दिन"}[lang]
    if days < 30:
        w = max(1, int(round(days / 7)))
        return {"en": f"{w} week{'s' if w != 1 else ''}", "hinglish": f"{w} hafte", "hi": f"{w} हफ़्ते"}[lang]
    if days < 365:
        m = max(1, int(round(days / 30)))
        return {"en": f"{m} month{'s' if m != 1 else ''}", "hinglish": f"{m} mahine", "hi": f"{m} महीने"}[lang]
    y = max(1, int(round(days / 365)))
    return {"en": f"{y} year{'s' if y != 1 else ''}", "hinglish": f"{y} saal", "hi": f"{y} साल"}[lang]


def _join(items: list[str], language: str) -> str:
    """English: "Fever with cough and vomiting". Hindi / Hinglish: "Bukhar, khansi aur ulti"."""
    if len(items) <= 1:
        return "".join(items)
    if language == "en":
        rest = [i.lower() for i in items[1:]]
        tail = rest[0] if len(rest) == 1 else ", ".join(rest[:-1]) + " and " + rest[-1]
        return f"{items[0]} with {tail}"
    return ", ".join(items[:-1]) + AND[language] + items[-1]


def _symptom_phrase(ex: Extraction, language: str) -> str:
    lang = lang_of(language)
    labels = [h.entry.label_for(lang) for h in ex.symptoms] + [h.entry.label_for(lang) for h in ex.services]
    if lang != "en":
        labels = [labels[0]] + [label[0].lower() + label[1:] if lang == "hinglish" else label for label in labels[1:]]
    return _join(labels, lang)


def reasoning(ex: Extraction, care: str, urgency: str, breathing: str, language: str) -> str:
    lang = lang_of(language)
    what = _symptom_phrase(ex, lang)
    dur = duration_label(ex.duration_days, lang)
    respiratory = any(h.entry.meta.get("respiratory") for h in ex.symptoms) or "fever" in ex.symptom_ids()
    note = (BREATHING_NOTE[breathing][lang] if respiratory and breathing in BREATHING_NOTE
            else NO_FLAGS_NOTE[lang])
    phrase = CARE_PHRASE[lang].get((care, urgency), "")
    if lang == "en":
        if dur:
            what += " today" if dur == "today" else f" for {dur}"
        if ex.age_group in ("infant", "child", "older_adult"):
            what += {"infant": " in a baby", "child": " in a child", "older_adult": " in an older adult"}[ex.age_group]
        return f"{what}; {note}, so {phrase}."
    lead = f"{dur} se {what.lower() if lang == 'hinglish' else what}" if dur and dur not in ("aaj se", "आज से") else what
    if lang == "hi" and dur and dur != "आज से":
        lead = f"{dur} से {what}"
    end = "।" if lang == "hi" else "."
    return f"{lead}, {note}{end} {phrase}"


def emergency_reasoning(flag_labels_en: list[str], flag_labels_local: list[str], language: str) -> tuple[str, str]:
    en = (f"Possible emergency signs: {', '.join(l.lower() for l in flag_labels_en)}. "
          "Do not wait for a booking: call 112 now (ambulance 102 in Delhi).")
    lang = lang_of(language)
    local = {
        "en": en,
        "hinglish": f"Emergency ke lakshan: {', '.join(flag_labels_local)}. Booking ka intezaar mat karein, "
                    "abhi 112 par call karein (Delhi mein ambulance 102).",
        "hi": f"इमरजेंसी के लक्षण: {', '.join(flag_labels_local)}। बुकिंग का इंतज़ार न करें, "
              "अभी 112 पर कॉल करें (दिल्ली में एम्बुलेंस 102)।",
    }[lang]
    return en, local


def emergency_block(flag_ids: list[str], language: str) -> dict:
    lang = lang_of(language)
    numbers = []
    for fid in flag_ids:
        if fid in FLAG_HELPLINES:
            h = FLAG_HELPLINES[fid]
            numbers.append({"label": h["label"], "label_local": h["label_hi"] if lang != "en" else h["label"],
                            "number": h["number"]})
    numbers = [{"label": n["label"], "label_local": n["label_hi"] if lang != "en" else n["label"],
                "number": n["number"]} for n in EMERGENCY_NUMBERS] + numbers
    return {
        "title": EMERGENCY_TITLE["en"],
        "title_local": EMERGENCY_TITLE[lang],
        "numbers": numbers,
        "steps": EMERGENCY_STEPS["en"],
        "steps_local": EMERGENCY_STEPS[lang],
    }


_BANNED = re.compile(
    r"\b(\d+\s?(mg|ml|mcg)|paracetamol|crocin|dolo|ibuprofen|antibiotic\w*|azithro\w*|amoxi\w*|"
    r"pneumonia|dengue|malaria|typhoid|covid|tuberculosis|cancer|diagnos\w*|prescri\w*)\b",
    re.IGNORECASE,
)


def scrub(text: str) -> str:
    """Remove medicine names, doses and disease names from generated text."""
    return re.sub(r"\s{2,}", " ", _BANNED.sub("", text or "")).strip()

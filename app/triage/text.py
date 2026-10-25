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
# thoughts of self-harm: the person reading may be the one at risk, so the steps speak to them too
SELF_HARM_FLAGS = ("self_harm_risk", "psychiatric_emergency")
SELF_HARM_STEPS = {
    "en": ["If you are thinking of hurting yourself, call Tele-MANAS 14416 or 112 now. You are not alone.",
           "If it is someone else, stay with them and remove anything they could hurt themselves with.",
           "Keep your phone on and share your location."],
    "hinglish": ["Agar aap khud ko nuksan pahunchane ka soch rahe hain, abhi Tele-MANAS 14416 ya 112 par call "
                 "karein. Aap akele nahi hain.",
                 "Agar yeh kisi aur ke liye hai, unke saath rahein aur aisi cheezein hata dein jinse woh khud ko "
                 "nuksan pahuncha sakein.",
                 "Phone chalu rakhein aur location share karein."],
    "hi": ["अगर आप ख़ुद को नुकसान पहुँचाने का सोच रहे हैं, तो अभी टेली-मानस 14416 या 112 पर कॉल करें। आप अकेले नहीं हैं।",
           "अगर यह किसी और के लिए है, तो उनके साथ रहें और ऐसी चीज़ें हटा दें जिनसे वे ख़ुद को नुकसान पहुँचा सकें।",
           "फ़ोन चालू रखें और लोकेशन शेयर करें।"],
}
# helpline labels in Devanagari for Hindi (config's label_hi is Hinglish)
NUMBER_LABEL_HI = {"112": "इमरजेंसी (पूरे भारत में)", "102": "दिल्ली एम्बुलेंस (CATS, मुफ़्त)",
                   "108": "कई राज्यों में एम्बुलेंस", "14416": "टेली-मानस हेल्पलाइन",
                   "1800-116-117": "एम्स ज़हर हेल्पलाइन"}
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


def _phrase(labels: list[str], lang: str) -> str:
    if lang != "en" and labels:
        labels = [labels[0]] + [label[0].lower() + label[1:] if lang == "hinglish" else label for label in labels[1:]]
    return _join(labels, lang)


def _symptom_phrase(ex: Extraction, language: str) -> str:
    lang = lang_of(language)
    return _phrase([h.entry.label_for(lang) for h in ex.symptoms] + [h.entry.label_for(lang) for h in ex.services],
                   lang)


# the model decided but no symptom or service was named in words we know
BASED_ON = {"en": "Based on your message", "hinglish": "Aapke sandesh ke hisaab se", "hi": "आपके संदेश के हिसाब से"}


def reasoning(ex: Extraction, care: str, urgency: str, breathing: str, language: str,
              labels: list[str] | None = None) -> str:
    """`labels` (in `language`) replace the extraction's symptoms and services, for a
    decision the fine-tuned model made from words the lexicon does not know."""
    lang = lang_of(language)
    what = _phrase(labels, lang) if labels is not None else _symptom_phrase(ex, lang)
    if not what:
        phrase = CARE_PHRASE[lang].get((care, urgency), "")
        if lang == "en":
            return f"{BASED_ON[lang]}; {NO_FLAGS_NOTE[lang]}, so {phrase}."
        return f"{BASED_ON[lang]}, {NO_FLAGS_NOTE[lang]}{'।' if lang == 'hi' else '.'} {phrase}"
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


def emergency_steps(flag_ids: list[str], language: str) -> list[str]:
    """What to do now; for thoughts of self-harm they speak to the writer as well."""
    steps = SELF_HARM_STEPS if any(f in SELF_HARM_FLAGS for f in flag_ids) else EMERGENCY_STEPS
    return steps[lang_of(language)]


def emergency_block(flag_ids: list[str], language: str) -> dict:
    lang = lang_of(language)

    def local(n: dict) -> str:  # Hindi in Devanagari, Hinglish in Roman script
        if lang == "hi":
            return NUMBER_LABEL_HI.get(n["number"], n["label_hi"])
        return n["label"] if lang == "en" else n["label_hi"]

    numbers = []
    for fid in flag_ids:
        if fid in FLAG_HELPLINES and FLAG_HELPLINES[fid]["number"] not in {n["number"] for n in numbers}:
            h = FLAG_HELPLINES[fid]
            numbers.append({"label": h["label"], "label_local": local(h), "number": h["number"]})
    general = [{"label": n["label"], "label_local": local(n), "number": n["number"]} for n in EMERGENCY_NUMBERS]
    # thoughts of self-harm: Tele-MANAS first
    numbers = numbers + general if any(f in SELF_HARM_FLAGS for f in flag_ids) else general + numbers
    return {
        "title": EMERGENCY_TITLE["en"],
        "title_local": EMERGENCY_TITLE[lang],
        "numbers": numbers,
        "steps": emergency_steps(flag_ids, "en"),
        "steps_local": emergency_steps(flag_ids, lang),
    }


_BANNED = re.compile(
    r"\b(\d+\s?(mg|ml|mcg)|paracetamol|crocin|dolo|ibuprofen|antibiotic\w*|azithro\w*|amoxi\w*|"
    r"pneumonia|dengue|malaria|typhoid|covid|tuberculosis|cancer|diagnos\w*|prescri\w*)\b",
    re.IGNORECASE,
)


def scrub(text: str) -> str:
    """Remove medicine names, doses and disease names from generated text."""
    return re.sub(r"\s{2,}", " ", _BANNED.sub("", text or "")).strip()


def has_banned(text: str) -> bool:
    """Would `scrub` remove something (the clinical-scope guardrail)?"""
    return bool(_BANNED.search(text or ""))


# ---- intake ("structured" in the trace) -------------------------------------

WHO_LABELS = {
    "self": {"en": "The person writing", "hinglish": "Aap khud", "hi": "आप ख़ुद"},
    "adult": {"en": "Adult", "hinglish": "Bade (adult)", "hi": "वयस्क"},
    "elderly": {"en": "Older adult", "hinglish": "Buzurg", "hi": "बुज़ुर्ग"},
    "child": {"en": "Child", "hinglish": "Bachcha", "hi": "बच्चा"},
    "infant": {"en": "Baby", "hinglish": "Chhota baby", "hi": "छोटा शिशु"},
    "pregnant": {"en": "Pregnant woman", "hinglish": "Garbhvati mahila", "hi": "गर्भवती महिला"},
    "unknown": {"en": "Not known yet", "hinglish": "Abhi pata nahi", "hi": "अभी पता नहीं"},
}
# the model's tags that have no lexicon entry of the same id
TAG_LABELS = {
    "breathlessness": {"en": "Breathing difficulty", "hinglish": "Saans lene mein dikkat", "hi": "सांस लेने में दिक्कत"},
    "bleeding": {"en": "Bleeding", "hinglish": "Khoon behna", "hi": "खून बहना"},
    "suicidal": {"en": "Thoughts of self-harm", "hinglish": "Khud ko nuksan ke khayal", "hi": "ख़ुद को नुकसान के ख़याल"},
    "dehydration": {"en": "Dehydration", "hinglish": "Paani ki kami", "hi": "पानी की कमी"},
    "pregnancy": {"en": "Pregnancy", "hinglish": "Pregnancy", "hi": "गर्भावस्था"},
    "burn": {"en": "Burn", "hinglish": "Jalna", "hi": "जलना"},
    "allergy": {"en": "Allergy", "hinglish": "Allergy", "hi": "एलर्जी"},
    "head_injury": {"en": "Head injury", "hinglish": "Sir mein chot", "hi": "सिर में चोट"},
}


def tag_label(tag: str, language: str) -> str:
    lang = lang_of(language)
    if tag in TAG_LABELS:
        return TAG_LABELS[tag][lang]
    return tag.replace("_", " ").capitalize()


# ---- guardrails (trace.guardrails) -----------------------------------------
# label, then the note for each status, in three languages

GUARDRAILS: dict[str, dict[str, dict[str, str]]] = {
    "safety_net": {
        "label": {"en": "Danger-sign rules", "hinglish": "Khatre ke lakshan ke niyam", "hi": "ख़तरे के लक्षणों के नियम"},
        "pass": {"en": "No danger sign found in the words used.",
                 "hinglish": "Likhi baat mein koi khatre ka lakshan nahi mila.",
                 "hi": "लिखी बात में कोई ख़तरे का लक्षण नहीं मिला।"},
        "fired": {"en": "A danger sign was found, so this goes straight to emergency help.",
                  "hinglish": "Khatre ka lakshan mila, isliye seedha emergency madad.",
                  "hi": "ख़तरे का लक्षण मिला, इसलिए सीधे इमरजेंसी मदद।"},
    },
    "model_emergency": {
        "label": {"en": "Model emergency check", "hinglish": "Model ki emergency jaanch", "hi": "मॉडल की इमरजेंसी जाँच"},
        "pass": {"en": "The model found no sign of an emergency.", "hinglish": "Model ko emergency nahi lagi.",
                 "hi": "मॉडल को इमरजेंसी नहीं लगी।"},
        "fired": {"en": "The model found signs of an emergency.", "hinglish": "Model ko emergency ke lakshan lage.",
                  "hi": "मॉडल को इमरजेंसी के लक्षण लगे।"},
    },
    "vulnerable_floor": {
        "label": {"en": "Baby, older adult or pregnancy", "hinglish": "Baby, buzurg ya pregnancy",
                  "hi": "शिशु, बुज़ुर्ग या गर्भावस्था"},
        "pass": {"en": "Nothing here needs a sooner visit because of age or pregnancy.",
                 "hinglish": "Umar ya pregnancy ki wajah se jaldi ki zarurat nahi.",
                 "hi": "उम्र या गर्भावस्था की वजह से जल्दी की ज़रूरत नहीं।"},
        "fired": {"en": "A baby, an older adult or a pregnancy: seen today at the latest.",
                  "hinglish": "Baby, buzurg ya pregnancy: aaj hi dekhna zaroori.",
                  "hi": "शिशु, बुज़ुर्ग या गर्भावस्था: आज ही देखना ज़रूरी।"},
    },
    "urgency_floor": {
        "label": {"en": "Urgency never lowered", "hinglish": "Jaldi kabhi kam nahi", "hi": "जल्दी कभी कम नहीं"},
        "pass": {"en": "The safety rules did not ask for a sooner time.",
                 "hinglish": "Safety niyamon ne pehle ka time nahi maanga.",
                 "hi": "सुरक्षा नियमों ने पहले का समय नहीं माँगा।"},
        "fired": {"en": "The safety rules asked for a sooner time, so it was moved up.",
                  "hinglish": "Safety niyamon ne pehle ka time maanga, isliye jaldi kiya.",
                  "hi": "सुरक्षा नियमों ने पहले का समय माँगा, इसलिए जल्दी किया।"},
    },
    "low_confidence": {
        "label": {"en": "Model confidence", "hinglish": "Model ka bharosa", "hi": "मॉडल का भरोसा"},
        "pass": {"en": "The model is sure enough to decide.", "hinglish": "Model faisle ke liye kaafi pakka hai.",
                 "hi": "मॉडल फ़ैसले के लिए काफ़ी पक्का है।"},
        "fired": {"en": "The model was unsure, so a safer route was taken.",
                  "hinglish": "Model pakka nahi tha, isliye surakshit raasta liya.",
                  "hi": "मॉडल पक्का नहीं था, इसलिए सुरक्षित रास्ता लिया।"},
    },
    "not_understood": {
        "label": {"en": "Words understood", "hinglish": "Baat samjhi gayi", "hi": "बात समझी गई"},
        "pass": {"en": "The words name a symptom, a service or a danger sign we know.",
                 "hinglish": "Shabdon mein koi pehchani taklif, service ya khatre ka lakshan hai.",
                 "hi": "शब्दों में कोई पहचानी तकलीफ़, सेवा या ख़तरे का लक्षण है।"},
        "fired": {"en": "Nothing medical was recognised in the words, so the model's guess was not trusted.",
                  "hinglish": "Shabdon mein kuch medical samajh nahi aaya, isliye model ke andaaze par bharosa nahi kiya.",
                  "hi": "शब्दों में कुछ मेडिकल समझ नहीं आया, इसलिए मॉडल के अंदाज़े पर भरोसा नहीं किया।"},
    },
    "out_of_scope": {
        "label": {"en": "Home health care only", "hinglish": "Sirf ghar pe health care", "hi": "सिर्फ़ घर पर स्वास्थ्य देखभाल"},
        "pass": {"en": "This is a health care request.", "hinglish": "Yeh health care ki baat hai.",
                 "hi": "यह स्वास्थ्य देखभाल की बात है।"},
        "fired": {"en": "This does not look like a home health care request.",
                  "hinglish": "Yeh ghar pe health care ki request nahi lagti.",
                  "hi": "यह घर पर स्वास्थ्य देखभाल का अनुरोध नहीं लगता।"},
    },
    "llm_fallback": {
        "label": {"en": "Second opinion (Claude)", "hinglish": "Doosri raay (Claude)", "hi": "दूसरी राय (Claude)"},
        "pass": {"en": "Not needed.", "hinglish": "Zarurat nahi padi.", "hi": "ज़रूरत नहीं पड़ी।"},
        "fired": {"en": "The model was unsure, so Claude gave a second opinion.",
                  "hinglish": "Model pakka nahi tha, isliye Claude se doosri raay li.",
                  "hi": "मॉडल पक्का नहीं था, इसलिए Claude से दूसरी राय ली।"},
    },
    "clinical_scope": {
        "label": {"en": "No diagnosis, no medicines", "hinglish": "Na bimari ka naam, na dawai",
                  "hi": "न बीमारी का नाम, न दवा"},
        "pass": {"en": "The reply names no disease and no medicine.",
                 "hinglish": "Jawab mein na bimari ka naam hai, na dawai ka.",
                 "hi": "जवाब में न बीमारी का नाम है, न दवा का।"},
        "fired": {"en": "A disease or medicine name was taken out of the reply.",
                  "hinglish": "Jawab se bimari ya dawai ka naam hataya gaya.",
                  "hi": "जवाब से बीमारी या दवा का नाम हटाया गया।"},
    },
    "invariants": {
        "label": {"en": "Final safety checks", "hinglish": "Aakhri safety jaanch", "hi": "आख़िरी सुरक्षा जाँच"},
        "pass": {"en": "An emergency never gets a booking; nothing else is marked as an emergency.",
                 "hinglish": "Emergency mein booking nahi; baaki kuch emergency nahi bataya.",
                 "hi": "इमरजेंसी में बुकिंग नहीं; बाकी कुछ इमरजेंसी नहीं बताया।"},
        "fired": {"en": "The reply was corrected to keep the safety rules.",
                  "hinglish": "Safety niyam ke liye jawab theek kiya gaya.",
                  "hi": "सुरक्षा नियम के लिए जवाब ठीक किया गया।"},
    },
}
GUARDRAILS["fever_home_visit"] = {
    "label": {"en": "Fever gets a home check", "hinglish": "Bukhar mein ghar par jaanch", "hi": "बुखार में घर पर जाँच"},
    "pass": {"en": "No fever was sent to a phone call only.", "hinglish": "Bukhar ko sirf phone call par nahi bheja.",
             "hi": "बुखार को सिर्फ़ फ़ोन कॉल पर नहीं भेजा।"},
    "fired": {"en": "Fever: a medic visit instead of only a phone call, as in the organisers' labels.",
              "hinglish": "Bukhar hai, isliye sirf phone call nahi, medic ghar aayenge.",
              "hi": "बुखार है, इसलिए सिर्फ़ फ़ोन कॉल नहीं, मेडिक घर आएँगे।"},
}
GUARDRAIL_IDS = list(GUARDRAILS)


def guardrails(fired: set[str], language: str) -> list[dict]:
    """Every guardrail with its status for this request ("fired" when it changed or
    decided something, else "pass")."""
    lang = lang_of(language)
    out = []
    for gid, g in GUARDRAILS.items():
        status = "fired" if gid in fired else "pass"
        out.append({"id": gid, "label": g["label"]["en"], "label_local": g["label"][lang], "status": status,
                    "note": g[status]["en"], "note_local": g[status][lang]})
    return out


# ---- safety-netting advice for non-emergency decisions ---------------------

def safety_net(language: str, fever: bool = False, child: bool = False, duration_days: float | None = None) -> str:
    """When to come back or call 112. Plain words, no diagnosis. A fever already 3 days or
    older does not get "if it lasts more than 3 days" (it already has)."""
    lang = lang_of(language)
    long_fever = fever and duration_days is not None and duration_days >= 3
    if lang == "en":
        extra = ", or the child becomes very drowsy or stops feeding" if child else ""
        tail = (", or the fever gets worse" if long_fever else ", or the fever lasts more than 3 days" if fever
                else ", or things get worse")
        return f"If there is trouble breathing, chest pain or fainting{extra}{tail}, call 112 right away or tell us."
    if lang == "hi":
        extra = ", बच्चा बहुत सुस्त हो जाए या दूध / खाना छोड़ दे" if child else ""
        tail = (", या बुखार बढ़ जाए" if long_fever else ", या बुखार 3 दिन से ज़्यादा रहे" if fever
                else ", या तकलीफ़ बढ़ जाए")
        return f"अगर सांस लेने में दिक्कत, सीने में दर्द या बेहोशी हो{extra}{tail}, तो तुरंत 112 पर कॉल करें या हमें बताएँ।"
    extra = ", bachcha bahut sust ho jaye ya doodh / khana chhod de" if child else ""
    tail = (", ya bukhar badh jaye" if long_fever else ", ya bukhar 3 din se zyada rahe" if fever
            else ", ya taklif badh jaye")
    return (f"Agar saans lene mein dikkat, seene mein dard, behoshi{extra}{tail}, "
            "to turant 112 par call karein ya hamein batayein.")


def speech_lang(language: str) -> str:
    """Read-aloud language: Hinglish is spoken from the Hindi (Devanagari) text,
    because a Hindi voice reads Roman-script Hindi with English sounds."""
    return "en" if lang_of(language) == "en" else "hi"


def speech(parts: list[str], language: str) -> dict:
    """Text for read-aloud, cleaned for a voice: sentence ends, "/" as "or",
    no brackets, and phone numbers digit by digit (112 is "1 1 2", not "one hundred twelve")."""
    sl = speech_lang(language)
    end = "।" if sl == "hi" else "."
    said = []
    for p in parts:
        p = scrub(p or "").strip()
        if p:
            said.append(p if p[-1] in ".!?।" else p + end)
    s = " ".join(said).replace(" / ", " या " if sl == "hi" else " or ")
    s = re.sub(r"[()]", "", s)
    s = re.sub(r"\b\d{3,}\b", lambda m: " ".join(m.group()), s)
    return {"locale": "en-IN" if sl == "en" else "hi-IN", "text": re.sub(r"\s{2,}", " ", s).strip()}

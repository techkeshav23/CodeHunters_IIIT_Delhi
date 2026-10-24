"""Structured facts from the user's words: red flags, symptoms, services,
who the patient is, age, duration and severity."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from functools import lru_cache

from .lexicon import Hit, Lexicon, Pattern, get_lexicon
from .normalize import BOUNDARY, COMMA, Text, analyse, detect_language, phon, tokenize

# Natural spellings; turned into canonical tokens once (see _tables).
_NUMBER_WORDS = {
    "ek": 1, "one": 1, "a": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "four": 4,
    "paanch": 5, "five": 5, "chhe": 6, "chah": 6, "six": 6, "saat": 7, "seven": 7, "aath": 8,
    "eight": 8, "nau": 9, "nine": 9, "das": 10, "ten": 10, "gyarah": 11, "barah": 12, "twelve": 12,
    "pandrah": 15, "fifteen": 15, "bees": 20, "twenty": 20, "tees": 30, "thirty": 30,
    "dedh": 1.5, "dhai": 2.5, "dhaai": 2.5,
}
_UNITS = {
    "din": 1, "dino": 1, "dinon": 1, "day": 1, "days": 1,
    "hafta": 7, "hafte": 7, "hafton": 7, "week": 7, "weeks": 7,
    "mahina": 30, "mahine": 30, "mahino": 30, "mahinon": 30, "month": 30, "months": 30,
    "saal": 365, "saalon": 365, "year": 365, "years": 365, "yr": 365, "yrs": 365,
    "ghanta": 1 / 24, "ghante": 1 / 24, "ghanton": 1 / 24, "hour": 1 / 24, "hours": 1 / 24, "hrs": 1 / 24,
}
_DURATION_AFTER = ["se", "since", "from", "ho", "hue", "hua"]
_DURATION_BEFORE = ["for", "since", "pichle", "pichhle", "last", "past"]
_RELATIVE_DURATIONS = [
    ("kal raat se", 1), ("kal se", 1), ("parso se", 2), ("since yesterday", 1), ("last night", 1),
    ("aaj subah se", 0), ("aaj se", 0), ("subah se", 0), ("abhi abhi", 0), ("just now", 0),
    ("since morning", 0), ("this morning", 0), ("today", 0), ("kai din", 7), ("bahut din", 7),
    ("kaafi din", 7), ("kai hafte", 21), ("kai mahine", 60), ("mahino se", 60), ("saalon se", 365),
    ("for months", 60), ("for years", 365), ("for weeks", 21),
    ("purana", 60), ("purani", 60), ("chronic", 60), ("long time", 60), ("kaafi samay se", 30),
    ("bahut samay se", 30),
]
_YOUNGER = ["chhota", "chhote", "chhoti", "kam"]  # "3 mahine se chhota" = younger than 3 months
_DIABETIC = ["diabetic", "diabetes", "madhumeh", "insulin", "sugar ke patient", "sugar ki bimari"]
_HEAT = ["dhoop", "sun", "garmi", "heat", "loo", "हीट"]
BP_EMERGENCY = 180  # systolic reading that counts as a red flag on its own
_PREGNANT_PATTERNS = ["pregnant", "pet se hai", "pet se hain", "garbh", "garbhavastha", "expecting",
                      "ummeed se hai", "ummeed se hain", "trimester"]
# "expecting your call / a call / improvement / the report" is not a pregnancy
_NOT_EXPECTING = ["call", "callback", "calls", "result", "results", "report", "reports", "reply", "response",
                  "visit", "visitor", "visitors", "guest", "guests", "improvement", "salary", "parcel", "doctor",
                  "your", "you", "news", "money", "payment", "message", "update", "relief", "recovery"]
_NOT_TRIMESTER = ["exam", "exams", "test", "tests", "semester", "term", "fees", "result"]
_PREG_PAST = ["tha", "thi", "the", "was", "were", "had"]  # "wife expecting thi pichle saal"
# "8th month", "7 va mahina", "aathva mahina": a month of pregnancy when a woman is named
# ("biwi 8th month mein hai"), not "mujhe 2nd month se sar dard" or "gym ka 3rd month"
_ORDINAL_SUFFIX = ["th", "st", "nd", "rd", "va", "vaan", "vi", "ve"]
_ORDINAL_WORDS = {"chhatha": 6, "satva": 7, "satvan": 7, "aathva": 8, "aathvan": 8, "nauva": 9, "nauvan": 9}
_FEMALE = ["wife", "biwi", "patni", "bahu", "bhabhi", "behen", "didi", "beti", "she", "her", "mummy", "bhabi"]
_CHILD_WORDS = ["bachcha"]  # beta/beti may be adults
# a child word names the patient when it owns something or is owned: "bachche ko", "mera bachcha"
_CHILD_OWNER_AFTER = ["ko", "ka", "ki", "ke", "ne", "mein", "me"]
_CHILD_OWNER_BEFORE = ["mera", "meri", "mere", "hamara", "hamari", "humara", "chhota", "chhoti", "chhote",
                       "my", "our", "little", "small"]
_CHILD_NOT_AFTER = ["nahi", "hui", "hue", "hua", "bade", "badi", "bada"]  # "bachi hui dawai", "bachche bade ho gaye"
_CHILD_VERB_SURFACE = {"bachne", "bachke", "bachkar", "bachao", "bachaao", "bachna", "bachaya", "bachana"}
# Childbirth in the last weeks: "delivery ko 6 din hue", "delivery ke 10 din baad", "postpartum"
_BIRTH_WORDS = ["delivery", "prasav", "c section", "cesarean", "caesarean"]
_BIRTH_AFTER = ["baad", "hue", "hui", "hua", "ho", "after", "since", "ago", "pehle"]
_BIRTH_ALWAYS = ["postpartum", "post partum", "gave birth", "just delivered"]
POSTPARTUM_DAYS = 60

# Numbers read off a device ("pulse 38", "heart rate 170", "oxygen 86", "BP 80/50", "sugar 45",
# "104 bukhar"). Each kind keeps its last reading ("oxygen 85 tha, ab 96 hai" -> 96).
_VITAL_WORDS = {
    "oximeter": ["pulse oximeter", "oximeter", "oxymeter"],
    "pulse": ["pulse", "pulse rate", "nabz", "nabj", "nadi", "dhadkan", "heart rate", "heartrate", "heart beat",
              "heartbeat", "bpm"],
    "spo2": ["spo2", "sp02", "oxygen", "oxygen level", "o2", "saturation", "sats"],
    "sugar": ["sugar", "glucose", "rbs", "fbs", "glucometer"],
    "temp": ["bukhar", "temperature", "temp", "tapman"],
    "bp": ["bp", "blood pressure"],
}
_VITAL_NUMBER_BEFORE = ["bpm", "bukhar", "temperature", "temp"]  # "170 bpm", "104 bukhar"
_NOT_A_READING = ["min", "mins", "minute", "minutes", "mg", "ml", "baar", "times", "tablet", "goli", "units"]
PULSE_LOW, PULSE_HIGH = 40, 150          # adults, with symptoms
SPO2_LOW = 90
SBP_SHOCK, SBP_LOW = 80, 90              # systolic <= 80 with symptoms, or < 90 with a pulse >= 110
SUGAR_LOW = 54
CHILD_FEVER_F = 104

# Past-tense and present-tense words (canonical) for third-party and "if" sentences
_PAST_WORDS = ["kal", "tha", "thi", "was", "were", "had", "ago", "pichle", "pichhle", "last", "yesterday"]
_PRESENT_WORDS = ["hai", "hain", "he", "h", "raha", "rahi", "rahe", "is", "are", "am", "s", "m"]
_IF_WORDS = ["agar", "if", "yadi"]
_THEN_WORDS = ["to", "toh", "then", "tab"]
_REQUEST_PAST = ["tha", "thi", "was", "were", "had", "ago"]  # "was in ICU", "ambulance aayi thi"
# Chest-wall pain is only considered in a young adult without these
CHEST_WALL_MAX_AGE = 40
_CARDIAC_COMPANIONS = {"sweating", "dizziness", "vomiting", "palpitations"}
_CONTEXT_ONLY = {"chest_wall", "third_party", "report"}  # phrase lists that are not severity words


@lru_cache(maxsize=1)
def _tables() -> dict:
    lex = get_lexicon()

    def k(word: str) -> tuple[str, ...]:
        return tuple(lex.canon(t) for t in tokenize(word))

    vital_phrases = sorted(((kind, k(w)) for kind, words in _VITAL_WORDS.items() for w in words),
                           key=lambda x: -len(x[1]))
    return {
        "numbers": {k(w)[0]: v for w, v in _NUMBER_WORDS.items()},
        "units": {k(w)[0]: v for w, v in _UNITS.items()},
        "dur_after": {k(w)[0] for w in _DURATION_AFTER},
        "dur_before": {k(w)[0] for w in _DURATION_BEFORE},
        "relative": [(k(w), d) for w, d in _RELATIVE_DURATIONS],
        "younger": {k(w)[0] for w in _YOUNGER},
        "diabetic": [k(w) for w in _DIABETIC],
        "heat": {k(w)[0] for w in _HEAT},
        "bp": k("bp")[0],
        "pregnant": [k(w) for w in _PREGNANT_PATTERNS],
        "ordinal_suffix": {k(w)[0] for w in _ORDINAL_SUFFIX},
        "ordinal_words": {k(w)[0]: v for w, v in _ORDINAL_WORDS.items()},
        "along": k("along")[0],
        "blood": k("khoon")[0],
        "blood_test": {k(w)[0] for w in ("kami", "jaanch", "janch", "test", "report", "group", "sugar",
                                         "badhana", "chadhana", "donate", "count")},
        "expecting": k("expecting"),
        "not_expecting": {k(w)[0] for w in _NOT_EXPECTING},
        "trimester": k("trimester"),
        "not_trimester": {k(w)[0] for w in _NOT_TRIMESTER},
        "preg_past": {k(w)[0] for w in _PREG_PAST},
        "female": {k(w)[0] for w in _FEMALE},
        "child": {k(w)[0] for w in _CHILD_WORDS},
        "child_after": {k(w)[0] for w in _CHILD_OWNER_AFTER},
        "child_before": {k(w)[0] for w in _CHILD_OWNER_BEFORE},
        "child_not_after": {k(w)[0] for w in _CHILD_NOT_AFTER},
        "birth": [k(w) for w in _BIRTH_WORDS],
        "birth_after": {k(w)[0] for w in _BIRTH_AFTER},
        "birth_always": [k(w) for w in _BIRTH_ALWAYS],
        "vitals": vital_phrases,
        "vital_before": {k(w)[0] for w in _VITAL_NUMBER_BEFORE},
        "not_reading": {k(w)[0] for w in _NOT_A_READING},
        "past_words": {k(w)[0] for w in _PAST_WORDS},
        "request_past": {k(w)[0] for w in _REQUEST_PAST},
        "present_words": {k(w)[0] for w in _PRESENT_WORDS},
        "if_words": {k(w)[0] for w in _IF_WORDS},
        "then_words": {k(w)[0] for w in _THEN_WORDS},
        "chal": k("chal")[0],
        "sequence": {k(w)[0] for w in ("phir", "fir", "then", "baad", "uske", "afterwards")},
        "medicine": {k(w)[0] for w in ("dawai", "treatment", "ilaj", "course", "dose", "chemo", "dialysis",
                                       "tb", "operation", "physio", "naukri", "job", "gym", "school", "training")},
        "male": {k(w)[0] for w in ("papa", "pita", "beta", "bete", "bhai", "dada", "dadaji", "nana", "chacha",
                                   "mama", "pati", "husband", "son", "father", "brother")},
        "preg_context": {k(w)[0] for w in ("hone", "pregnant", "garbh", "delivery", "expecting", "doosra",
                                           "dusra", "second", "pehla", "first", "tisra", "third")},
    }


@dataclass
class Extraction:
    text: Text
    tokens: list[str]                     # canonical tokens
    red_flags: list[Hit] = field(default_factory=list)          # confirmed (not negated, conditions met)
    negated_flags: set[str] = field(default_factory=set)
    settled_flags: set[str] = field(default_factory=set)       # happened earlier and has settled: same-day check
    symptoms: list[Hit] = field(default_factory=list)
    negated_symptoms: set[str] = field(default_factory=set)
    services: list[Hit] = field(default_factory=list)
    severity: set[str] = field(default_factory=set)
    relation: str | None = None
    relation_label: str | None = None
    age_years: float | None = None
    age_group: str | None = None
    pregnant: bool | None = None
    duration_days: float | None = None

    @property
    def language(self) -> str:
        return self.text.language

    def symptom_ids(self) -> list[str]:
        return [h.id for h in self.symptoms]

    def service_ids(self) -> list[str]:
        return [h.id for h in self.services]


def _number(tok: str, numbers: dict) -> float | None:
    if tok.replace(".", "", 1).isdigit():
        return float(tok)
    return numbers.get(tok)


def _contains(tokens: list[str], pat: tuple[str, ...]) -> bool:
    k = len(pat)
    return any(tuple(tokens[j:j + k]) == pat for j in range(len(tokens) - k + 1))


def _ages_and_durations(tokens: list[str], lex: Lexicon) -> tuple[float | None, float | None, bool]:
    """Returns (age_years, duration_days, saw_pregnancy_months)."""
    tb = _tables()
    numbers, units = tb["numbers"], tb["units"]
    age = duration = None
    preg_months = False
    relation_tokens = {t for e in lex.entries["relation"] for p in e.patterns for t in p.tokens}
    symptom_tokens = {p.tokens[0] for e in lex.entries["symptom"] for p in e.patterns}
    n = len(tokens)
    for i, tok in enumerate(tokens):
        if tok in ("umar", "age") and i + 1 < n and tokens[i + 1].isdigit():
            # "umar 2 mahine", "age 6 weeks": the unit decides; a bare number is years
            unit = units.get(tokens[i + 2]) if i + 2 < n else None
            years = float(tokens[i + 1]) * (unit / 365 if unit else 1)
            age = age if age is not None else years
            continue
        ordinal = tok in tb["ordinal_words"]
        val = tb["ordinal_words"][tok] if ordinal else _number(tok, numbers)
        if val is None or i + 1 >= n:
            continue
        j = i + 1
        prev = tokens[i - 1] if i > 0 else ""
        if tokens[j] in tb["ordinal_suffix"] and j + 1 < n and tokens[j + 1] in units:
            j += 1  # "8 th month", "7 va mahina"
            ordinal = True
        if tokens[j] not in units:
            # "2-3 din": skip the second number
            if j + 1 < n and _number(tokens[j], numbers) is not None and tokens[j + 1] in units:
                j += 1
            else:
                # "Papa 62 ke hai"
                if (prev in relation_tokens and tokens[j] in ("ka", "ki", "ke") and j + 1 < n
                        and tokens[j + 1] in ("hai", "hain", "he", "h") and 1 <= val <= 110 and tok.isdigit()):
                    age = age if age is not None else val
                continue
        unit_days = units[tokens[j]]
        days = val * unit_days
        nxt = tokens[j + 1] if j + 1 < n else ""
        nxt2 = tokens[j + 2] if j + 2 < n else ""
        if nxt == "pregnant" or (nxt in ("ki", "ke", "ka") and nxt2 == "pregnant"):
            preg_months = True
            continue
        # "wife ka 7 month chal raha hai", "7 months along", "8th month" (month of pregnancy),
        # not "dawai 3 mahine chal rahi"; "bachche ka 8th month" is the baby's age
        if (nxt in (tb["chal"], tb["along"]) or ordinal) and 25 <= unit_days <= 31 and 1 <= val <= 10:
            near = tokens[max(0, i - 6):i]
            woman = any(t in tb["female"] for t in near)
            # "second baby ka 8 month chal raha", "baby hone wala hai": the pregnancy, not the baby's age
            expecting = woman or bool(tb["preg_context"] & set(tokens))
            if any(t in tb["child"] for t in near) and not expecting:
                age = age if age is not None else days / 365
                continue
            other = any(t in tb["medicine"] or t in tb["male"] for t in near)  # chemo, dialysis, papa, beta
            if (not (other and not woman) and nxt not in tb["dur_after"] and nxt not in tb["preg_past"]
                    and (nxt in (tb["chal"], tb["along"]) or woman)):
                preg_months = True
                continue
        if nxt in tb["dur_after"] and nxt2 in tb["younger"]:
            age = age if age is not None else days * 0.95 / 365
            continue
        is_duration = (nxt in tb["dur_after"] or prev in tb["dur_before"]
                       or (nxt in ("ka", "ki", "ke") and nxt2 in symptom_tokens))
        is_age = (nxt == "old" or (nxt in ("ka", "ki", "ke") and nxt2 not in symptom_tokens
                                   and (nxt2 in relation_tokens or nxt2 in tb["child"]
                                        or nxt2 in ("hai", "hain", "he", BOUNDARY, ""))))
        if is_age and not is_duration:
            age = age if age is not None else days / 365
        elif not is_duration and unit_days >= 365 and val >= 10:
            age = age if age is not None else val
        else:
            duration = duration if duration is not None else days
    if duration is None:
        for pat, days in tb["relative"]:
            if _contains(tokens, pat):
                duration = float(days)
                break
    return age, duration, preg_months


RESOLVABLE = {"chest_pain", "breathing_difficulty", "major_injury"}
_PAST_TENSE = {phon(w) for w in ("tha", "thi", "the", "pehle", "was", "were", "had")}
_NOT = {"not", "no", "na", "nahi", "never"}
_MAYBE = {"could", "maybe", "might", "may", "shayad", "kya", "if", "agar", "whether", "possibly"}
_POSSIBLE = {phon(w) for w in ("possibility", "possible", "chance", "chances")}


def _pregnant_now(tokens: list[str]) -> bool:
    """A plain "pregnant" mention, not "I am not pregnant" or "could she be pregnant?"."""
    patterns = _tables()["pregnant"]
    for i in range(len(tokens)):
        pat = next((p for p in patterns if tuple(tokens[i:i + len(p)]) == p), None)
        if pat is None:
            continue
        tb = _tables()
        before = set(tokens[max(0, i - 3):i])
        after = tokens[i + len(pat):i + len(pat) + 2]
        nxt = after[0] if after else ""
        if pat == tb["expecting"] and tb["not_expecting"] & set(tokens[i + 1:i + 4]):  # "expecting your call"
            continue
        if pat == tb["trimester"] and nxt in tb["not_trimester"]:  # "trimester exams"
            continue
        clause_after = []
        for t in tokens[i + len(pat):i + len(pat) + 4]:
            if t in (BOUNDARY, COMMA):
                break
            clause_after.append(t)
        if any(t in tb["preg_past"] for t in clause_after):  # "expecting thi pichle saal"
            continue
        if before & _NOT or "nahi" in after:
            continue
        if before & _MAYBE or tuple(after) in {("ho", "sakti"), ("ho", "sakta")}:
            continue
        if after[:1] and after[0] in _POSSIBLE:  # "no fever, discharge, pregnancy possibility"
            continue
        return True
    return False


def _child_is_patient(tokens: list[str], surface: list[str]) -> bool:
    """"bachche ko bukhar", "mera bachcha sust hai"; not "bachi hui dawai", "garmi se bachne",
    "bachcha nahi hai ghar mein" or "mere bachche bade ho gaye"."""
    tb = _tables()
    for i, tok in enumerate(tokens):
        if tok not in tb["child"] or (i < len(surface) and surface[i].lower() in _CHILD_VERB_SURFACE):
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        prev = tokens[i - 1] if i > 0 else ""
        if nxt in tb["child_not_after"] or tb["preg_context"] & set(tokens[max(0, i - 3):i + 3]):
            continue  # "expecting her 2nd child", "baby hone wala hai" is about a pregnancy
        if nxt in tb["child_after"] or prev in tb["child_before"]:
            return True
    return False


def _negated_next_to(tokens: list[str], h: Hit, lex: Lexicon) -> bool:
    """"tez dard nahi", "no severe pain": a negation word touching the phrase."""
    nxt = tokens[h.end] if h.end < len(tokens) else ""
    prev = tokens[h.start - 1] if h.start > 0 else ""
    # not the tag "na" of "dard hai na bahut tez" ("isn't it, very bad")
    return nxt in lex.neg_after or (prev in lex.neg_before and prev != "na")


def _clause_ids(tokens: list[str], marks: tuple[str, ...] = (BOUNDARY, COMMA)) -> list[int]:
    """Clause number for each token; commas and sentence ends start a new clause.
    With marks=(BOUNDARY,) it numbers sentences instead."""
    out, n = [], 0
    for t in tokens:
        if t in marks:
            n += 1
        out.append(n)
    return out


def _postpartum(tokens: list[str]) -> bool:
    """Childbirth in the last weeks: "delivery ko 6 din hue", "delivery ke 10 din baad se"."""
    tb = _tables()
    if any(_contains(tokens, p) for p in tb["birth_always"]):
        return True
    n = len(tokens)
    for pat in tb["birth"]:
        k = len(pat)
        for i in range(n - k + 1):
            if tuple(tokens[i:i + k]) != pat:
                continue
            window = tokens[i + k:i + k + 6]
            before = tokens[max(0, i - 2):i]
            if not (set(window) & tb["birth_after"] or {"after", "since"} & set(before)):
                continue
            # "delivery 2 saal pehle hui thi" is not recent
            days = None
            for j, w in enumerate(window[:-1]):
                v = _number(w, tb["numbers"])
                if v is not None and window[j + 1] in tb["units"]:
                    days = v * tb["units"][window[j + 1]]
                    break
            if days is None or days <= POSTPARTUM_DAYS:
                return True
    return False


def _hypothetical_if(tokens: list[str], start: int) -> bool:
    """Inside an "if" clause that is not happening now: "agar saans phoole ya hoth neele pade to
    turant hospital le jana", "if she gets breathless, call 112". "Agar saans phool rahi hai to
    kya karein" is happening now and stays a red flag."""
    tb = _tables()
    for k in range(start - 1, max(-1, start - 13), -1):
        t = tokens[k]
        if t == BOUNDARY or t in tb["then_words"]:
            return False
        if t in tb["if_words"]:
            span = []
            for w in tokens[k + 1:]:
                if w == BOUNDARY or w in tb["then_words"]:
                    break
                span.append(w)
            if start >= k + 1 + len(span):
                return False
            return not any(w in tb["present_words"] for w in span)
    return False


def _pair_ok(h: Hit, cands: list[Hit], tokens: list[str]) -> bool:
    """`requires: [pair]`: another sign of the same red flag from a different group."""
    for g in cands:
        if g is h or g.id != h.id or g.pattern.group is None or g.pattern.group == h.pattern.group:
            continue
        if g.start < h.end and h.start < g.end:  # the same words
            continue
        if h.pattern.pair_with and g.pattern.group not in h.pattern.pair_with:
            continue
        if g.pattern.pair_with and h.pattern.group not in g.pattern.pair_with:
            continue
        limits = [w for w in (h.pattern.pair_within, g.pattern.pair_within) if w is not None]
        if limits:
            # close together and one event: "harpic ki bottle se pi liya", not
            # "harpic se bathroom saaf kiya, phir khana kha liya"
            lo, hi = min(h.end, g.end), max(h.start, g.start)
            if hi - lo > min(limits) or any(t == BOUNDARY or t in _tables()["sequence"] for t in tokens[lo:hi]):
                continue
        return True
    return False


def _readings(tokens: list[str], surface: list[str]) -> dict[str, tuple[float, int, int]]:
    """Last number given for each vital sign: kind -> (value, start, end)."""
    tb = _tables()
    out: dict[str, tuple[float, int, int]] = {}
    n, i = len(tokens), 0
    while i < n:
        hit = next(((kind, p) for kind, p in tb["vitals"] if tuple(tokens[i:i + len(p)]) == p), None)
        if hit is None:
            i += 1
            continue
        kind, p = hit
        end = i + len(p)
        found = None
        for j in range(end, min(n, end + 5)):  # "pulse 38", "oxygen level 86", "BP: 80/50", "pulse oximeter pe 38"
            w = tokens[j]
            if w == BOUNDARY and j == end and surface[j] == ":":
                continue
            if w in (BOUNDARY, COMMA):
                break
            if w.replace(".", "", 1).isdigit():
                if j + 1 < n and (tokens[j + 1] in tb["units"] or tokens[j + 1] in tb["not_reading"]):
                    break
                found = (float(w), j)
                break
        if found is None and p[-1] in tb["vital_before"]:  # "170 bpm", "104 bukhar", "104 ka bukhar"
            for j in range(i - 1, max(-1, i - 4), -1):
                w = tokens[j]
                if w in (BOUNDARY, COMMA):
                    break
                if w.replace(".", "", 1).isdigit():
                    found = (float(w), j)
                    break
        if found is not None:
            value, j = found
            prev = out.get(kind)
            if prev is None or j >= prev[1]:
                out[kind] = (value, min(i, j), max(end, j + 1))
        i = end
    return out


def _vital_flags(ex: "Extraction", readings: dict, symptomatic: bool) -> list[tuple[str, int, int]]:
    """Dangerous readings: (kind, start, end) for each."""
    young_infant = ex.age_years is not None and ex.age_years < 1
    child = ex.age_group in ("infant", "child")
    lo = 60 if young_infant else PULSE_LOW
    hi = 200 if young_infant else 180 if child else PULSE_HIGH
    out = []
    pulse = readings.get("pulse")
    if pulse and 20 <= pulse[0] <= 250 and symptomatic and (pulse[0] < lo or pulse[0] > hi):
        out.append(("pulse",) + pulse[1:])
    spo2 = readings.get("spo2")
    if spo2 and 40 <= spo2[0] < SPO2_LOW:
        out.append(("spo2",) + spo2[1:])
    oxi = readings.get("oximeter")  # one number from a pulse oximeter: oxygen or pulse, both are bad here
    if oxi and 20 <= oxi[0] <= 250 and symptomatic and (oxi[0] < SPO2_LOW or oxi[0] > hi):
        out.append(("oximeter",) + oxi[1:])
    bp = readings.get("bp")
    fast = pulse is not None and pulse[0] >= 110
    if bp and 40 <= bp[0] < SBP_LOW and symptomatic and (bp[0] <= SBP_SHOCK or fast):
        out.append(("bp",) + bp[1:])
    sugar = readings.get("sugar")
    if sugar and 15 <= sugar[0] < SUGAR_LOW:
        out.append(("sugar",) + sugar[1:])
    temp = readings.get("temp")
    if temp and child:
        f = temp[0] * 9 / 5 + 32 if 34 <= temp[0] <= 43 else temp[0]
        if CHILD_FEVER_F <= f <= 110:
            out.append(("temp",) + temp[1:])
    return out


def age_group_for(age_years: float | None) -> str | None:
    if age_years is None:
        return None
    if age_years < 1:
        return "infant"
    if age_years < 13:
        return "child"
    if age_years < 60:
        return "adult"
    return "older_adult"


def extract(text: str, language_hint: str = "auto", lex: Lexicon | None = None,
            age_years: float | None = None, duration_days: float | None = None) -> Extraction:
    """`age_years` / `duration_days` come from answers to our follow-up
    questions and override what the free text says."""
    lex = lex or get_lexicon()
    t = analyse(text, language_hint)
    # text typed or dictated without spaces: "saansnahiaaraheinbehoshhogayehain"
    t.tokens, t.surface = lex.split_runs(t.tokens, t.surface)
    tokens = lex.canon_tokens(t.tokens)
    ex = Extraction(text=t, tokens=tokens)

    # who the patient is
    rel_hits = lex.find(tokens, t.surface, "relation")
    if rel_hits:
        first = next((h for h in rel_hits if h.id != "self"), rel_hits[0])
        ex.relation = first.id
        ex.relation_label = first.evidence.title()

    ex.age_years, ex.duration_days, preg_months = _ages_and_durations(tokens, lex)
    if age_years is not None:
        ex.age_years = age_years
    if duration_days is not None:
        ex.duration_days = duration_days
    if ex.age_years is None:
        if any(h.id == "infant" for h in rel_hits) or "navjaat" in tokens:
            ex.age_years = 0.05
        elif any(h.id in ("grandparent", "elderly") for h in rel_hits):
            ex.age_group = "older_adult"
        elif _child_is_patient(tokens, t.surface):
            ex.age_group = "child"
    if ex.age_years is not None:
        ex.age_group = age_group_for(ex.age_years)

    ex.pregnant = True if preg_months or _pregnant_now(tokens) else None

    # modifiers, kept with positions so "severe" applies only near a symptom;
    # "koi tez dard nahi" is not severe (only a negation right next to it: in
    # "achanak kuch yaad nahi" the "nahi" belongs to the symptom, not to "achanak")
    mod_hits = [h for h in lex.find(tokens, t.surface, "modifier")
                if not (h.id == "severe" and _negated_next_to(tokens, h, lex))]
    for h in mod_hits:
        if h.id not in _CONTEXT_ONLY:
            ex.severity.add(h.id)

    # "chakkar, behoshi ya seene mein dard kuch nahi hai": the closing "nahi" covers the whole list
    sym_hits = lex.find(tokens, t.surface, "symptom")
    # "khoon ki kami / jaanch / report" is a deficiency or a test, not bleeding
    lab = _tables()["blood_test"]
    flag_hits = [h for h in lex.find(tokens, t.surface, "red_flag")
                 if not (h.pattern.tokens[-1] == _tables()["blood"] and lab & set(tokens[h.end:h.end + 3]))]
    # from the text itself, not the client's language hint
    lex.negate_or_lists(sym_hits + flag_hits, tokens, english=detect_language(text) == "en")

    # symptoms and services
    for h in sym_hits:
        if h.negated:
            ex.negated_symptoms.add(h.id)
        elif h.id not in ex.symptom_ids():
            ex.symptoms.append(h)
    if any(h.entry.meta.get("generic") for h in ex.symptoms) and len(ex.symptoms) > 1:
        ex.symptoms = [h for h in ex.symptoms if not h.entry.meta.get("generic")]
    for h in lex.find(tokens, t.surface, "service"):
        if not h.negated and h.id not in ex.service_ids():
            ex.services.append(h)

    # red flags, with their conditions
    context = set()
    if ex.age_years is not None and ex.age_years < 0.25:
        context.add("infant")
    if ex.age_years is not None and ex.age_years < 1:
        context.add("baby")
    if ex.age_group in ("infant", "child"):
        context.add("child")
    if ex.age_group == "older_adult":
        context.add("older_adult")
    if ex.pregnant:
        context.add("pregnant")
    if "fever" in ex.symptom_ids():
        context.add("fever")
    tb = _tables()
    if any(_contains(tokens, p) for p in tb["diabetic"]):
        context.add("diabetic")
    if any(tok in tb["heat"] for tok in tokens):
        context.add("heat")
    if ("severe" in ex.severity or "vomiting" in ex.symptom_ids() or "dhundhla" in tokens
            or "blurred" in tokens or "sina" in tokens):
        context.add("bp_danger")
    if _postpartum(tokens):
        context.add("postpartum")
    if "palpitations" in ex.symptom_ids():
        context.add("palpitations")
    for i, tok in enumerate(tokens):  # "BP 200 ho gaya"
        if tok == tb["bp"]:
            for j in range(i + 1, min(len(tokens), i + 4)):
                if tokens[j].isdigit() and int(tokens[j]) >= BP_EMERGENCY:
                    entry = lex.by_id["severe_bp"]
                    ex.red_flags.append(Hit(entry=entry, start=i, end=j + 1,
                                            pattern=Pattern(f"bp >= {BP_EMERGENCY}", ("bp",), False),
                                            negated=False, evidence=" ".join(t.surface[i:j + 1])))
                    break
            if ex.red_flags:
                break
    clause = _clause_ids(tokens)
    sentence = _clause_ids(tokens, (BOUNDARY,))
    past = [m for m in mod_hits if m.id == "past"]
    current = [m for m in mod_hits if m.id == "current"]
    mild = [m for m in mod_hits if m.id == "mild"]
    # a year ("heart attack in 2019") places its phrase in the past
    this_year = datetime.date.today().year
    past_at = [m.start for m in past] + [i for i, tok in enumerate(tokens)
                                         if tok.isdigit() and len(tok) == 4 and 1950 <= int(tok) < this_year]
    for h in flag_hits:
        # "agar saans phoole ... to hospital le jana": a doctor's what-if, not a symptom now
        if not h.negated and _hypothetical_if(tokens, h.start):
            h.negated = True
    in_past = {id(h) for h in flag_hits
               if any(clause[p] == clause[h.start] for p in past_at)
               and not any(clause[m.start] == clause[h.start] for m in current)}
    cands = [h for h in flag_hits if not h.negated and id(h) not in in_past]
    for h in flag_hits:
        if h.negated:
            ex.negated_flags.add(h.id)
            continue
        req = h.pattern.requires
        if req:
            ok = False
            for r in req:
                if r in ("severe", "sudden"):
                    ok = ok or lex.near([m for m in mod_hits if m.id == r], tokens, h.start, h.end)
                elif r == "pair":
                    ok = ok or _pair_ok(h, cands, tokens)
                else:
                    ok = ok or r in context
            # "mild lower abdominal pain" in pregnancy is not an emergency by itself
            if not ok or lex.near(mild, tokens, h.start, h.end):
                continue
        # "seizure disorder years ago", "pichle saal heart attack hua tha"
        same = clause[h.start]
        if any(clause[p] == same for p in past_at) and not any(clause[m.start] == same for m in current):
            continue
        if h.id not in [f.id for f in ex.red_flags]:
            ex.red_flags.append(h)
    _drop_other_people(ex, tokens, sentence, mod_hits, rel_hits)
    _drop_past_requests(ex, tokens, sentence, current)
    # "pehle seene mein dard laga tha ... gas thi ... ab bilkul theek": a past, settled episode of
    # chest pain or breathlessness is a same-day check, not an emergency (fainting, stroke signs etc. stay)
    if "resolved" in ex.severity:
        keep = []
        for h in ex.red_flags:
            # WhatsApp text often has no punctuation, so look at the words around the symptom
            around = set(tokens[max(0, h.start - 3):min(len(tokens), h.end + 6)])
            now = any(m.start >= h.start - 3 and m.start < h.end + 3 for m in current)
            settled = h.id in RESOLVABLE and around & _PAST_TENSE and not now
            if settled:
                ex.settled_flags.add(h.id)
            else:
                keep.append(h)
        ex.red_flags = keep
    long_standing = ex.duration_days is not None and ex.duration_days >= 14
    worse_now = "severe" in ex.severity or "current" in ex.severity  # "this episode is different, now..."
    if long_standing and "episodic" in ex.severity and not worse_now:  # "sometimes breathless, for 3 months"
        ex.red_flags = [h for h in ex.red_flags if h.id not in ("breathing_difficulty", "chest_pain")]
    if "resolved" in ex.severity:  # "biscuit kha liya, ab theek": drop only the soft flags
        ex.red_flags = [h for h in ex.red_flags if not h.entry.meta.get("soft")]

    # numbers: "pulse 38", "heart rate 170", "oxygen 86", "BP 80/50 with pulse 140", "sugar 45"
    symptomatic = bool(ex.red_flags) or any(not h.entry.meta.get("condition") for h in ex.symptoms)
    for kind, start, end in _vital_flags(ex, _readings(tokens, t.surface), symptomatic):
        if kind == "sugar" and "resolved" in ex.severity:  # "sugar 50 thi, juice diya, ab theek"
            continue
        if "abnormal_vitals" not in [f.id for f in ex.red_flags]:
            ex.red_flags.append(Hit(entry=lex.by_id["abnormal_vitals"], start=start, end=end,
                                    pattern=Pattern(f"{kind} reading", (kind,), False), negated=False,
                                    evidence=" ".join(t.surface[start:end])))

    # "dabane pe dard hota hai aur haath upar karne pe" after a gym day in a 24-year-old:
    # chest-wall strain, a same-day check. Not with sweating, breathlessness, dizziness or vomiting.
    if (any(h.id == "chest_pain" for h in ex.red_flags) and ex.age_years is not None
            and ex.age_years < CHEST_WALL_MAX_AGE and any(m.id == "chest_wall" for m in mod_hits)
            and all(h.id == "chest_pain" for h in ex.red_flags)
            and not _CARDIAC_COMPANIONS & set(ex.symptom_ids())):
        ex.red_flags = []
        ex.settled_flags.add("chest_pain")
    ex.negated_flags -= {f.id for f in ex.red_flags}
    return ex


def _drop_other_people(ex: Extraction, tokens: list[str], sentence: list[int], mod_hits: list[Hit],
                       rel_hits: list[Hit]) -> None:
    """"Padosi wale uncle ko kal raat paralysis ka attack aaya ... papa ke liye poochna tha",
    "TV pe dekha ek aadmi ko heart attack aa gaya ... kya papa ka bhi ECG": a red flag in a
    sentence about someone else, told in the past or from the news, while the message is about
    a family member named in another sentence. Kept if that sentence says it is happening now."""
    if not ex.red_flags:
        return
    tb = _tables()
    # checked per sentence, then per comma-separated clause
    # ("padosi ko pichle hafte heart attack aaya tha, mere papa ka BP check karwana hai")
    for unit in (sentence, _clause_ids(tokens)):
        drop: set[int] = set()
        for s in {unit[h.start] for h in ex.red_flags}:
            words = [tok for tok, si in zip(tokens, unit) if si == s]
            mods = {m.id for m in mod_hits if unit[m.start] == s}
            if "third_party" not in mods:
                continue
            told = "report" in mods or "past" in mods or bool(set(words) & tb["past_words"])
            now = "current" in mods or bool(set(words) & tb["present_words"])
            patient_elsewhere = any(unit[r.start] != s for r in rel_hits)
            if told and not now and patient_elsewhere:
                drop.add(s)
        if drop:
            ex.red_flags = [h for h in ex.red_flags if unit[h.start] not in drop]


def _drop_past_requests(ex: Extraction, tokens: list[str], sentence: list[int], current: list[Hit]) -> None:
    """"She was in ICU for a week last winter", "ambulance aayi thi": an ambulance or ICU in the
    past is history, not a request for one now (kept if the same sentence says now / abhi)."""
    tb = _tables()
    keep = []
    for h in ex.red_flags:
        if h.id == "emergency_requested":
            s = sentence[h.start]
            words = {tok for tok, si in zip(tokens, sentence) if si == s}
            if words & tb["request_past"] and not any(sentence[m.start] == s for m in current):
                continue
        keep.append(h)
    ex.red_flags = keep

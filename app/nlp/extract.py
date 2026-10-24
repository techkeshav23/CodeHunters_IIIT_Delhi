"""Structured facts from the user's words: red flags, symptoms, services,
who the patient is, age, duration and severity."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .lexicon import Hit, Lexicon, get_lexicon
from .normalize import BOUNDARY, Text, analyse, tokenize

# Natural spellings; turned into canonical tokens once (see _tables).
_NUMBER_WORDS = {
    "ek": 1, "one": 1, "a": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "four": 4,
    "paanch": 5, "five": 5, "chhe": 6, "chah": 6, "six": 6, "saat": 7, "seven": 7, "aath": 8,
    "eight": 8, "nau": 9, "nine": 9, "das": 10, "ten": 10, "gyarah": 11, "barah": 12, "twelve": 12,
    "pandrah": 15, "fifteen": 15, "bees": 20, "twenty": 20, "tees": 30, "thirty": 30,
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
]
_PREGNANT_PATTERNS = ["pregnant", "pet se hai", "pet se hain", "garbh"]
CHILD_WORDS = {"bachcha"}  # canonical; beta/beti may be adults


@lru_cache(maxsize=1)
def _tables() -> dict:
    lex = get_lexicon()

    def k(word: str) -> tuple[str, ...]:
        return tuple(lex.canon(t) for t in tokenize(word))

    return {
        "numbers": {k(w)[0]: v for w, v in _NUMBER_WORDS.items()},
        "units": {k(w)[0]: v for w, v in _UNITS.items()},
        "dur_after": {k(w)[0] for w in _DURATION_AFTER},
        "dur_before": {k(w)[0] for w in _DURATION_BEFORE},
        "relative": [(k(w), d) for w, d in _RELATIVE_DURATIONS],
        "pregnant": [k(w) for w in _PREGNANT_PATTERNS],
    }


@dataclass
class Extraction:
    text: Text
    tokens: list[str]                     # canonical tokens
    red_flags: list[Hit] = field(default_factory=list)          # confirmed (not negated, conditions met)
    negated_flags: set[str] = field(default_factory=set)
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
            age = age if age is not None else float(tokens[i + 1])
            continue
        val = _number(tok, numbers)
        if val is None or i + 1 >= n:
            continue
        j = i + 1
        if tokens[j] not in units:
            # "2-3 din": skip the second number
            if j + 1 < n and _number(tokens[j], numbers) is not None and tokens[j + 1] in units:
                j += 1
            else:
                continue
        unit_days = units[tokens[j]]
        days = val * unit_days
        nxt = tokens[j + 1] if j + 1 < n else ""
        nxt2 = tokens[j + 2] if j + 2 < n else ""
        prev = tokens[i - 1] if i > 0 else ""
        if nxt in ("ki", "ke", "ka") and nxt2 == "pregnant":
            preg_months = True
            continue
        is_duration = (nxt in tb["dur_after"] or prev in tb["dur_before"]
                       or (nxt in ("ka", "ki", "ke") and nxt2 in symptom_tokens))
        is_age = (nxt == "old" or (nxt in ("ka", "ki", "ke") and nxt2 not in symptom_tokens
                                   and (nxt2 in relation_tokens or nxt2 in CHILD_WORDS
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
        elif any(tok in CHILD_WORDS for tok in tokens):
            ex.age_group = "child"
    if ex.age_years is not None:
        ex.age_group = age_group_for(ex.age_years)

    ex.pregnant = True if preg_months or any(_contains(tokens, p) for p in _tables()["pregnant"]) else None

    # modifiers, kept with positions so "severe" applies only near a symptom
    mod_hits = lex.find(tokens, t.surface, "modifier")
    for h in mod_hits:
        ex.severity.add(h.id)

    # symptoms and services
    for h in lex.find(tokens, t.surface, "symptom"):
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
    if ex.age_group in ("infant", "child"):
        context.add("child")
    if ex.age_group == "older_adult":
        context.add("older_adult")
    if ex.pregnant:
        context.add("pregnant")
    if "fever" in ex.symptom_ids():
        context.add("fever")
    for h in lex.find(tokens, t.surface, "red_flag"):
        if h.negated:
            ex.negated_flags.add(h.id)
            continue
        req = h.pattern.requires
        if req:
            ok = False
            for r in req:
                if r in ("severe", "sudden"):
                    ok = ok or lex.near([m for m in mod_hits if m.id == r], tokens, h.start, h.end)
                else:
                    ok = ok or r in context
            if not ok:
                continue
        if h.id not in [f.id for f in ex.red_flags]:
            ex.red_flags.append(h)
    ex.negated_flags -= {f.id for f in ex.red_flags}
    return ex

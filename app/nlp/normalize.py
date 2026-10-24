"""Tokenising, phonetic keys and language detection for English, Hindi
(Devanagari) and Hinglish (romanised Hindi)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .translit import devanagari_ratio, transliterate

BOUNDARY = "<b>"  # clause boundary token: . , ! ? ; and the Devanagari danda

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿"), None)
_TOKEN_RE = re.compile(r"[a-z]+|\d+(?:\.\d+)?|[.,!?;:\n]")
_PHON_REPLACE = [
    ("chch", "ch"), ("cch", "ch"), ("ph", "f"), ("w", "v"), ("q", "k"), ("z", "j"),
    ("ee", "i"), ("oo", "u"),
]

# Words that point to romanised Hindi (Hinglish) rather than English.
HINGLISH_MARKERS = {
    "hai", "hain", "ho", "hua", "hui", "hue", "ko", "se", "mein", "me", "mai", "ka", "ki", "ke",
    "nahi", "nahin", "nai", "nhi", "aur", "bhi", "raha", "rahi", "rahe", "gaya", "gayi", "gaye",
    "kya", "kuch", "bahut", "bohot", "abhi", "kal", "din", "mujhe", "mera", "meri", "mere",
    "unko", "usko", "unhe", "inko", "papa", "mummy", "dadi", "dada", "nani", "nana", "beta",
    "beti", "bachcha", "bacha", "dard", "bukhar", "khansi", "saans", "sans", "pet", "sar",
    "sir", "ulti", "dast", "chakkar", "kamzori", "jaldi", "chahiye", "lagwana", "karna",
    "ghar", "pe", "par", "tak", "wala", "wali", "thoda", "zyada", "jyada", "lag", "laga",
}
ENGLISH_MARKERS = {
    "the", "is", "are", "has", "have", "had", "my", "since", "for", "with", "and", "of",
    "he", "she", "i", "am", "not", "no", "pain", "fever", "cough", "days", "day", "weeks",
    "breathing", "please", "need", "want", "mother", "father", "son", "daughter", "wife",
    "husband", "from", "been", "very", "feeling", "having", "it", "in", "at", "to",
}


@dataclass
class Text:
    raw: str
    roman: str          # Devanagari transliterated, lower-case
    tokens: list[str]   # phonetic keys, with BOUNDARY tokens between clauses
    surface: list[str]  # the romanised words behind each token
    language: str       # "en" | "hi" | "hinglish"


def phon(token: str) -> str:
    """Phonetic key so common spelling variants meet: bukhaar/bukhar,
    khaansi/khansi, seene/sine, saans/sans, zyada/jyada, ulty/ulti."""
    t = token.lower()
    if not t or t == BOUNDARY or t.isdigit():
        return t
    for a, b in _PHON_REPLACE:
        t = t.replace(a, b)
    t = re.sub(r"(.)\1+", r"\1", t)
    if len(t) > 2 and t.endswith("y"):
        t = t[:-1] + "i"
    return t


def to_roman(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").translate(_ZERO_WIDTH)
    text = transliterate(text)
    # strip accents from Latin letters (e.g. "bukhār")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return text.lower()


def tokens_and_surface(text: str) -> tuple[list[str], list[str]]:
    """Phonetic keys plus the matching surface words (romanised, lower-case)."""
    roman = to_roman(text)
    # split letters from digits: "2din" -> "2 din", "103f" -> "103 f"
    roman = re.sub(r"(\d)([a-z])", r"\1 \2", roman)
    roman = re.sub(r"([a-z])(\d)", r"\1 \2", roman)
    keys: list[str] = []
    surface: list[str] = []
    for tok in _TOKEN_RE.findall(roman):
        if tok in ".,!?;:\n":
            if keys and keys[-1] != BOUNDARY:
                keys.append(BOUNDARY)
                surface.append(tok.strip() or ".")
            continue
        keys.append(phon(tok))
        surface.append(tok)
    return keys, surface


def tokenize(text: str) -> list[str]:
    return tokens_and_surface(text)[0]


def detect_language(text: str, hint: str = "auto") -> str:
    hint = (hint or "auto").strip().lower()
    ratio = devanagari_ratio(text or "")
    if hint in ("en", "english"):
        return "en"
    if hint in ("hinglish", "hi-latn", "hi_latn", "hindi-latin"):
        return "hinglish"
    if hint in ("hi", "hindi", "hi-in"):
        return "hi" if ratio >= 0.3 else "hinglish"
    if ratio >= 0.5:
        return "hi"
    words = re.findall(r"[a-z]+", to_roman(text))
    if not words:
        return "hi" if ratio > 0 else "en"
    hing = sum(1 for w in words if w in HINGLISH_MARKERS)
    eng = sum(1 for w in words if w in ENGLISH_MARKERS)
    if ratio > 0 or (hing >= 1 and hing >= 0.5 * eng):
        return "hinglish"
    return "en"


def analyse(text: str, hint: str = "auto") -> Text:
    keys, surface = tokens_and_surface(text)
    return Text(raw=text or "", roman=to_roman(text), tokens=keys, surface=surface,
                language=detect_language(text, hint))

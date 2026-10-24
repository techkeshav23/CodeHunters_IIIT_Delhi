"""Devanagari -> Hinglish-style Latin transliteration.

Goal: put Hindi script into the same space as romanised Hindi so one lexicon
covers both (बुखार -> "bukhaar", which normalises like "bukhar"). Not a
scholarly scheme: it follows how people type Hindi in Latin letters, with the
usual schwa deletion (दर्द -> "dard", धड़कन -> "dhadkan").
"""
from __future__ import annotations

SCHWA = "ə"

VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e",
}
MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e",
}
CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    # precomposed nukta letters
    "क़": "k", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "d", "ढ़": "dh", "फ़": "f", "य़": "y",
}
NUKTA_FORMS = {"क": "k", "ख": "kh", "ग": "g", "ज": "z", "ड": "d", "ढ": "dh", "फ": "f", "य": "y"}
NUKTA = "़"
VIRAMA = "्"
NASAL = {"ं": "n", "ँ": "n"}
VISARGA = "ः"
DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}
PUNCT = {"।": ".", "॥": "."}


def is_devanagari(ch: str) -> bool:
    return "ऀ" <= ch <= "ॿ"


def _word_units(word: str) -> list[list[str]]:
    """Split one Devanagari word into [consonant, vowel] units. A vowel of
    SCHWA means the inherent 'a', which may be deleted later."""
    units: list[list[str]] = []
    i = 0
    while i < len(word):
        ch = word[i]
        if ch in CONSONANTS:
            cons = CONSONANTS[ch]
            if i + 1 < len(word) and word[i + 1] == NUKTA:
                cons = NUKTA_FORMS.get(ch, cons)
                i += 1
            units.append([cons, SCHWA])
        elif ch in MATRAS and units:
            units[-1][1] = MATRAS[ch]
        elif ch == VIRAMA and units:
            units[-1][1] = ""
        elif ch in VOWELS:
            units.append(["", VOWELS[ch]])
        elif ch in NASAL and units:
            if units[-1][1] == SCHWA:
                units[-1][1] = "a"
            units[-1][1] += NASAL[ch]
        elif ch == VISARGA and units:
            units[-1][1] = (units[-1][1].replace(SCHWA, "a")) + "h"
        elif ch in DIGITS:
            units.append([DIGITS[ch], ""])
        i += 1
    _delete_schwas(units)
    return units


def _delete_schwas(units: list[list[str]]) -> None:
    if not units:
        return
    # Word-final inherent 'a' is silent, except in one-letter words (न -> "na").
    if len(units) > 1 and units[-1][1] == SCHWA and units[-1][0]:
        units[-1][1] = ""
    # Medial: V C(ə) C V -> V C C V (क-म-ज़ो-री -> kamzorii, ध-ड़-क-न -> dhadkan).
    for i in range(1, len(units) - 1):
        prev_has_vowel = units[i - 1][1] not in ("",)
        nxt = units[i + 1]
        if units[i][1] == SCHWA and units[i][0] and prev_has_vowel and nxt[0] and nxt[1] not in ("",):
            units[i][1] = ""


def transliterate(text: str) -> str:
    """Transliterate every Devanagari run in `text`; other characters pass through."""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            units = _word_units("".join(buf))
            out.append("".join(c + v.replace(SCHWA, "a") for c, v in units))
            buf.clear()

    for ch in text:
        if is_devanagari(ch) and ch not in PUNCT:
            buf.append(ch)
        else:
            flush()
            out.append(PUNCT.get(ch, ch))
    flush()
    return "".join(out)


def devanagari_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha() or is_devanagari(c)]
    if not letters:
        return 0.0
    return sum(1 for c in letters if is_devanagari(c)) / len(letters)

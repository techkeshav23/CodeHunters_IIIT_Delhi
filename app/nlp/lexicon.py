"""Loads app/data/lexicon.yaml and finds its patterns in tokenised text.

Matching works on phonetic tokens (normalize.phon) after alias mapping, so
"chest pain", "seene mein dard" and "सीने में दर्द" all become `seena dard`.
Pattern words must appear in order, with at most MAX_GAP other words between
them and never across a sentence boundary. Negation is checked around each
match ("saans lene mein koi dikkat nahi" is not a red flag).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from rapidfuzz import fuzz, process

from ..config import DATA_DIR
from .normalize import BOUNDARY, phon, tokenize

MAX_GAP = 2        # content words allowed between two pattern words
MAX_SPAN_GAP = 6   # total words allowed between two pattern words
# Small words that do not count towards MAX_GAP ("pet mein bahut tez dard",
# "pet ke neeche daayein taraf dard"). Stored as phonetic keys.
FILLERS = {phon(w) for w in (
    "mein me ho raha rahi rahe hai hain tha thi the ka ki ke ko pe bhi bahut tez thoda sa si se hi to "
    "in my of a an is his her on at uske unke mere meri mera neeche upar daayein baayein dayi bayi "
    "daahine taraf side right left hisse wale wali"
).split()}
NEG_WINDOW = 3
MOD_WINDOW = 3
FUZZY_MIN_LEN = 5
FUZZY_CUTOFF = 86


@dataclass(frozen=True)
class Pattern:
    text: str
    tokens: tuple[str, ...]
    has_negation: bool
    requires: tuple[str, ...] = ()


@dataclass
class Entry:
    id: str
    kind: str  # red_flag | symptom | service | modifier | relation
    label: str
    label_hinglish: str
    label_hi: str
    patterns: list[Pattern]
    meta: dict = field(default_factory=dict)
    exclude_if_before: frozenset[str] = frozenset()

    def label_for(self, language: str) -> str:
        return {"hi": self.label_hi, "hinglish": self.label_hinglish}.get(language, self.label)


@dataclass
class Hit:
    entry: Entry
    start: int
    end: int  # exclusive
    pattern: Pattern
    negated: bool
    evidence: str

    @property
    def id(self) -> str:
        return self.entry.id


class Lexicon:
    def __init__(self, path: Path | None = None):
        path = path or DATA_DIR / "lexicon.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        self.alias: dict[str, str] = {}
        for canon, variants in (data.get("aliases") or {}).items():
            c = phon(str(canon))
            self.alias[c] = c
            for v in variants:
                for t in tokenize(str(v)):
                    self.alias[t] = c

        neg = data.get("negation") or {}
        self.neg_after = {self._canon_plain(t) for w in neg.get("after", []) for t in tokenize(str(w))}
        self.neg_before = {self._canon_plain(t) for w in neg.get("before", []) for t in tokenize(str(w))}
        self.breakers = {self._canon_plain(t) for w in neg.get("breakers", []) for t in tokenize(str(w))}
        self.not_after = {self._canon_plain(t) for w in neg.get("not_after", []) for t in tokenize(str(w))}
        self.negation_words = self.neg_after | self.neg_before

        self.entries: dict[str, list[Entry]] = {"red_flag": [], "symptom": [], "service": [],
                                                "modifier": [], "relation": []}
        for item in data.get("red_flags") or []:
            self.entries["red_flag"].append(self._entry(item, "red_flag"))
        for item in data.get("symptoms") or []:
            self.entries["symptom"].append(self._entry(item, "symptom"))
        for item in data.get("services") or []:
            self.entries["service"].append(self._entry(item, "service"))
        for mod_id, words in (data.get("modifiers") or {}).items():
            self.entries["modifier"].append(self._entry({"id": mod_id, "patterns": words}, "modifier"))
        for rel_id, words in (data.get("relations") or {}).items():
            self.entries["relation"].append(self._entry({"id": rel_id, "patterns": words}, "relation"))

        self.by_id = {e.id: e for kind in self.entries.values() for e in kind}
        self.vocab = {t for kind in self.entries.values() for e in kind for p in e.patterns for t in p.tokens}
        self._vocab_long = sorted(t for t in self.vocab if len(t) >= FUZZY_MIN_LEN and not t.isdigit())
        self._first: dict[str, dict[str, list[tuple[Entry, Pattern]]]] = {}
        for kind, entries in self.entries.items():
            index: dict[str, list[tuple[Entry, Pattern]]] = {}
            for e in entries:
                for p in e.patterns:
                    index.setdefault(p.tokens[0], []).append((e, p))
            self._first[kind] = index

    # ---- building -------------------------------------------------------
    def _canon_plain(self, tok: str) -> str:
        return self.alias.get(tok, tok)

    def _pattern(self, text: str, requires: tuple[str, ...] = ()) -> Pattern | None:
        toks = tuple(self._canon_plain(t) for t in tokenize(text) if t != BOUNDARY)
        if not toks:
            return None
        has_neg = any(t in {"nahi", "not", "no", "na", "without", "t"} for t in toks)
        return Pattern(text=text, tokens=toks, has_negation=has_neg, requires=requires)

    def _entry(self, item: dict, kind: str) -> Entry:
        pats = [p for p in (self._pattern(str(t)) for t in item.get("patterns") or []) if p]
        for cond in item.get("conditional") or []:
            req = tuple(cond.get("requires") or ())
            pats += [p for p in (self._pattern(str(t), req) for t in cond.get("patterns") or []) if p]
        meta = {k: v for k, v in item.items() if k not in {"id", "label", "label_hinglish", "label_hi",
                                                            "patterns", "conditional", "exclude_if_before"}}
        excl = frozenset(self._canon_plain(phon(str(w))) for w in item.get("exclude_if_before") or [])
        label = item.get("label") or item["id"].replace("_", " ")
        return Entry(id=item["id"], kind=kind, label=label,
                     label_hinglish=item.get("label_hinglish") or label,
                     label_hi=item.get("label_hi") or item.get("label_hinglish") or label,
                     patterns=pats, meta=meta, exclude_if_before=excl)

    # ---- canonicalising input --------------------------------------------
    @lru_cache(maxsize=20000)
    def canon(self, tok: str) -> str:
        if tok == BOUNDARY or tok.isdigit():
            return tok
        c = self.alias.get(tok, tok)
        if c in self.vocab or c in self.negation_words or len(c) < FUZZY_MIN_LEN:
            return c
        best = process.extractOne(c, self._vocab_long, scorer=fuzz.ratio, score_cutoff=FUZZY_CUTOFF)
        if best and best[0][0] == c[0]:
            return best[0]
        # a typo of an alias spelling ("bukhaaar" is handled by phon, "khaansee" here)
        best = process.extractOne(c, [a for a in self.alias if len(a) >= FUZZY_MIN_LEN],
                                  scorer=fuzz.ratio, score_cutoff=FUZZY_CUTOFF + 4)
        if best and best[0][0] == c[0]:
            return self.alias[best[0]]
        return c

    def canon_tokens(self, tokens: list[str]) -> list[str]:
        return [self.canon(t) for t in tokens]

    # ---- matching -----------------------------------------------------------
    def find(self, tokens: list[str], surface: list[str], kind: str) -> list[Hit]:
        """All matches of `kind` entries in canonical `tokens`."""
        hits: list[Hit] = []
        index = self._first[kind]
        for i, tok in enumerate(tokens):
            for entry, pat in index.get(tok, ()):
                end = self._match_from(tokens, i, pat.tokens)
                if end is None:
                    continue
                if entry.exclude_if_before and any(t in entry.exclude_if_before for t in tokens[max(0, i - 2):i]):
                    continue
                negated = False if (pat.has_negation or kind in ("modifier", "relation")) else self._negated(tokens, i, end)
                hits.append(Hit(entry=entry, start=i, end=end, pattern=pat, negated=negated,
                                evidence=" ".join(surface[i:end])))
        return hits

    @staticmethod
    def _match_from(tokens: list[str], i: int, pat: tuple[str, ...]) -> int | None:
        pos = i
        for k, want in enumerate(pat):
            if k == 0:
                if tokens[pos] != want:
                    return None
                pos += 1
                continue
            found = None
            content = 0
            for j in range(pos, min(len(tokens), pos + MAX_SPAN_GAP + 1)):
                t = tokens[j]
                if t == BOUNDARY:
                    break
                if t == want:
                    found = j
                    break
                if t not in FILLERS:
                    content += 1
                    if content > MAX_GAP:
                        break
            if found is None:
                return None
            pos = found + 1
        return pos

    def _negated(self, tokens: list[str], start: int, end: int) -> bool:
        # inside the match: "dard nahi hai seene mein" (but not "dard kam nahi ... seene mein")
        for k in range(start + 1, end - 1):
            if tokens[k] in self.neg_after and tokens[k - 1] not in self.not_after:
                return True
        # after: "dikkat nahi", "dard to nahi hai" (but not "dard kam nahi ho raha")
        for k in range(end, min(len(tokens), end + NEG_WINDOW)):
            t = tokens[k]
            if t == BOUNDARY or t in self.breakers:
                break
            if t in self.neg_after:
                prev = tokens[k - 1] if k - 1 >= 0 else ""
                if prev in self.not_after:
                    return False
                return True
        # before: "no chest pain", "bina bukhar ke"
        for k in range(start - 1, max(-1, start - 1 - NEG_WINDOW), -1):
            t = tokens[k]
            if t == BOUNDARY or t in self.breakers:
                break
            if t in self.neg_before:
                return True
        return False

    def near(self, hits: list[Hit], tokens: list[str], start: int, end: int) -> bool:
        """True if any hit lies within MOD_WINDOW words of [start, end) in the same sentence."""
        lo, hi = start, end
        while lo > 0 and start - lo < MOD_WINDOW and tokens[lo - 1] != BOUNDARY:
            lo -= 1
        while hi < len(tokens) and hi - end < MOD_WINDOW and tokens[hi] != BOUNDARY:
            hi += 1
        return any(h.start < hi and h.end > lo for h in hits)


@lru_cache(maxsize=1)
def get_lexicon() -> Lexicon:
    return Lexicon()

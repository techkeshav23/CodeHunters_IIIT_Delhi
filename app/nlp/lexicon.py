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
from .normalize import BOUNDARY, COMMA, phon, tokenize

MAX_GAP = 2        # content words allowed between two pattern words
MAX_SPAN_GAP = 6   # total words allowed between two pattern words
# Small words that do not count towards MAX_GAP ("pet mein bahut tez dard",
# "pet ke neeche daayein taraf dard"). Stored as phonetic keys.
FILLERS = {phon(w) for w in (
    "mein me ho raha rahi rahe hai hain tha thi the ka ki ke ko pe bhi bahut tez thoda sa si se hi to "
    "in my of a an is his her on at uske unke mere meri mera neeche upar daayein baayein dayi bayi "
    "daahine taraf side right left hisse wale wali bilkul"
).split()}
NEG_WINDOW = 3     # words between "no" / "nahi" and the symptom
LIST_WINDOW = 30   # how far back a negated list can start ("No A, B, C, D or E")
LIST_ITEM = 6      # longest item inside such a list
MOD_WINDOW = 3
FUZZY_MIN_LEN = 5
FUZZY_CUTOFF = 86
# "suicide jaisa koi khayal nahi": words skipped right after a symptom before looking for "nahi"
NEG_SKIP = {phon(w) for w in "jaisa jaisi jaise koi aisa aisi".split()}
# "lakwa ho jaega" ("will get paralysed"), "behosh ho jaye to": a fear or a what-if, not a symptom
FUTURE = {phon(w) for w in "jaega jayega jaegi jayegi jaenge jayenge jaye jaaye".split()}
# "khud ko nuksan pahunchane ya suicide jaisa koi khayal nahi": one negation covers an "or" list
OR_WORDS = {"ya"}
OR_WORDS_EN = {"or"}  # Hinglish "or" often means "aur" (and), so only in English text
LIST_VERBS = {phon(w) for w in "hai hain he h tha thi the raha rahi rahe ho hua hui is are was".split()}
COUNT_WORDS = {phon(w) for w in ("once twice times baar din days day hafte weeks mahine months saal years "
                                 "ghante hours one two three four five ek do teen char paanch").split()}
# top-level phrase lists in lexicon.yaml, matched like modifiers (see extract.py for their use)
CONTEXT_LISTS = ("resolved", "past", "current", "episodic", "chest_wall", "third_party", "report")


@dataclass(frozen=True)
class Pattern:
    text: str
    tokens: tuple[str, ...]
    has_negation: bool
    requires: tuple[str, ...] = ()
    group: str | None = None            # conditional group, for `requires: [pair]`
    pair_with: tuple[str, ...] = ()     # groups this one may pair with (empty: any other group)
    pair_within: int | None = None      # partner must be at most this many words away
    exact: bool = False                 # written "=my water broke": no words in between


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
        for mod_id in CONTEXT_LISTS:
            self.entries["modifier"].append(self._entry({"id": mod_id, "patterns": data.get(mod_id) or []},
                                                        "modifier"))

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

    def _pattern(self, text: str, requires: tuple[str, ...] = (), group: str | None = None,
                 pair_with: tuple[str, ...] = (), pair_within: int | None = None) -> Pattern | None:
        exact = text.startswith("=")
        toks = tuple(self._canon_plain(t) for t in tokenize(text.lstrip("=")) if t not in (BOUNDARY, COMMA))
        if not toks:
            return None
        has_neg = any(t in {"nahi", "not", "no", "na", "without", "t"} for t in toks)
        return Pattern(text=text, tokens=toks, has_negation=has_neg, requires=requires,
                       group=group, pair_with=pair_with, pair_within=pair_within, exact=exact)

    def _entry(self, item: dict, kind: str) -> Entry:
        pats = [p for p in (self._pattern(str(t)) for t in item.get("patterns") or []) if p]
        for cond in item.get("conditional") or []:
            req = tuple(cond.get("requires") or ())
            group = cond.get("group")
            pair_with = tuple(cond.get("pair_with") or ())
            within = cond.get("pair_within")
            pats += [p for p in (self._pattern(str(t), req, group, pair_with, within)
                                 for t in cond.get("patterns") or []) if p]
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
        if tok in (BOUNDARY, COMMA) or tok.isdigit():
            return tok
        c = self.alias.get(tok, tok)
        # an alias is a deliberate spelling: "dauraan" means "dauran" (during), never fuzz it to "daura" (fit)
        if tok in self.alias or c in self.vocab or c in self.negation_words or len(c) < FUZZY_MIN_LEN:
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

    # ---- text without spaces ------------------------------------------------
    SHORT_PIECES = {"ho", "ko", "se", "ka", "ki", "ke", "me", "ne", "pe", "bp", "hi", "ab"}

    _COMMON = ("ho raha rahi rahe rahein hai hain he gaya gayi gaye gai ko ki ka ke se men mein nahi nahin "
               "bhi aur ab abhi ne par pe tha thi the kar liya li hua hui hue de do diya di ja jaa a aa "
               "mujhe unko usko unhe mera meri mere hum ham bahut kuch").split()

    @property
    def _seg_words(self) -> set[str]:
        if not hasattr(self, "_seg_cache"):
            words = set(self.vocab) | set(self.alias) | FILLERS | {phon(w) for w in self._COMMON}
            self._seg_cache = {w for w in words if w and not w.isdigit() and w not in (BOUNDARY, COMMA)}
        return self._seg_cache

    def _segment(self, word: str, exact: bool = False) -> list[str] | None:
        """Split a run-together word into known words; None if it does not split cleanly.
        `exact`: every letter must belong to a known word of 2+ letters ("chestpain", "seenemein")."""
        n, vocab = len(word), self._seg_words
        best: list[tuple[float, list[str]] | None] = [None] * (n + 1)
        best[0] = (0.0, [])
        for i in range(n):
            if best[i] is None:
                continue
            score, parts = best[i]
            for j in range(i + 1, min(n, i + 16) + 1):
                piece = word[i:j]
                # exact splits take two-letter pieces only from a short list ("dauraan" is not "daura an")
                short_ok = len(piece) > 2 or (len(piece) == 2 and (not exact or piece in self.SHORT_PIECES)) \
                    or (piece == "a" and not exact)
                if phon(piece) in vocab and short_ok:
                    cand = (score + len(piece) ** 2, parts + [piece])
                    if best[j] is None or cand[0] > best[j][0]:
                        best[j] = cand
            if exact:
                continue
            cand = (score - 3, parts + ["\0" + word[i]])  # skip one unknown character
            if best[i + 1] is None or cand[0] > best[i + 1][0]:
                best[i + 1] = cand
        if best[n] is None:
            return None
        parts = best[n][1]
        unknown = sum(1 for p in parts if p.startswith("\0"))
        if exact:
            # two or three whole words, at least one of them from the lexicon itself; a negation
            # only as the full last word ("saansnahi"), never "nikala" -> "ni kala" or "lagani" -> "laga ni"
            neg = [k for k, p in enumerate(parts) if self.canon(phon(p)) in self.negation_words]
            ok = (2 <= len(parts) <= 3
                  and any(len(p) >= 3 and (phon(p) in self.vocab or phon(p) in self.alias) for p in parts)
                  and all(k == len(parts) - 1 and parts[k] in ("nahi", "nahin", "nhi") for k in neg))
            return parts if ok else None
        if unknown > 0.15 * n or sum(1 for p in parts if not p.startswith("\0")) < 3:
            return None
        merged: list[str] = []
        for p in parts:  # glue unknown characters back onto their neighbour
            if p.startswith("\0"):
                if merged:
                    merged[-1] += p[1:]
                else:
                    merged.append(p[1:])
            else:
                merged.append(p)
        return merged

    def split_runs(self, tokens: list[str], surface: list[str], min_len: int = 12) -> tuple[list[str], list[str]]:
        out_t: list[str] = []
        out_s: list[str] = []
        for tok, surf in zip(tokens, surface):
            if (len(surf) >= 6 and tok not in self.vocab and tok not in self.alias and surf.isalpha()
                    and self.canon(tok) not in self.vocab):  # a typo of a known word stays one word
                # shorter runs ("chestpain", "saansnahi") must split into whole words
                parts = (self._segment(surf) if len(surf) >= min_len else None) or self._segment(surf, exact=True)
                if parts:
                    out_t += [phon(p) for p in parts]
                    out_s += parts
                    continue
            out_t.append(tok)
            out_s.append(surf)
        return out_t, out_s

    # ---- matching -----------------------------------------------------------
    def find(self, tokens: list[str], surface: list[str], kind: str) -> list[Hit]:
        """All matches of `kind` entries in canonical `tokens`."""
        hits: list[Hit] = []
        index = self._first[kind]
        for i, tok in enumerate(tokens):
            for entry, pat in index.get(tok, ()):
                # modifiers ("hosh mein hain", "ab theek") must not jump over a "nahi"
                end = self._match_from(tokens, i, pat.tokens, strict=kind == "modifier" or pat.exact)
                if end is None:
                    continue
                if entry.exclude_if_before and any(t in entry.exclude_if_before for t in tokens[max(0, i - 2):i]):
                    continue
                negated = False if (pat.has_negation or kind in ("modifier", "relation")) else self._negated(tokens, i, end)
                hits.append(Hit(entry=entry, start=i, end=end, pattern=pat, negated=negated,
                                evidence=" ".join(surface[i:end])))
        return hits

    def _match_from(self, tokens: list[str], i: int, pat: tuple[str, ...], strict: bool = False) -> int | None:
        pos = i
        for k, want in enumerate(pat):
            if k == 0:
                if tokens[pos] != want:
                    return None
                pos += 1
                continue
            # next to a negation word only small words may sit in between:
            # "not feeding" must not match "not blue and is feeding"
            max_gap = 0 if (strict or want in self.negation_words or pat[k - 1] in self.negation_words) else MAX_GAP
            found = None
            content = 0
            for j in range(pos, min(len(tokens), pos + MAX_SPAN_GAP + 1)):
                t = tokens[j]
                if t in (BOUNDARY, COMMA):
                    break
                if t == want:
                    found = j
                    break
                if t not in FILLERS:
                    content += 1
                    if content > max_gap:
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
        # after: "dikkat nahi", "dard to nahi hai" (but not "dard kam nahi ho raha"),
        # the fear form "stroke na ho" ("let it not be a stroke") and the future "lakwa ho jaega"
        skip = end
        while skip < len(tokens) and tokens[skip] in NEG_SKIP:  # "suicide jaisa koi khayal nahi"
            skip += 1
        for k in range(skip, min(len(tokens), skip + NEG_WINDOW)):
            t = tokens[k]
            if t in (BOUNDARY, COMMA) or t in self.breakers:
                break
            if t == "na" and k + 1 < len(tokens) and tokens[k + 1] in ("ho", "hua", "hoga", "hoye"):
                return True
            if k == end and t in ("ho", "a") and k + 1 < len(tokens) and tokens[k + 1] in FUTURE:
                return True
            if t in self.neg_after:
                prev = tokens[k - 1] if k - 1 >= 0 else ""
                if prev in self.not_after:
                    return False
                return True
        # a risk, not an event: "risk of stroke", "how to prevent a heart attack", "lakwe ka khatra"
        k = start - 1
        while k >= 0 and tokens[k] in ("a", "an", "the", "of"):
            k -= 1
        if k >= 0 and (tokens[k] in ("prevent", "avoid")
                       or (tokens[k] in ("risk", "chance", "chances") and tokens[k + 1] == "of")):
            return True
        # "lakwe ka khatra", "heart attack ka koi khatra nahi": talk about a risk, not a symptom
        if tokens[end:end + 1] in (["ka"], ["ki"], ["ke"]) and "khatra" in tokens[end + 1:end + 3]:
            return True
        # before: "no chest pain", "bina bukhar ke", and lists such as
        # "No weakness, numbness, slurred speech, chest pain or trouble breathing"
        in_list = False
        item_len = 0
        for k in range(start - 1, max(-1, start - 1 - LIST_WINDOW), -1):
            t = tokens[k]
            if t == BOUNDARY or t in self.breakers:
                return False
            if t == COMMA:
                in_list, item_len = True, 0
                continue
            if t in self.neg_before:
                # "No, he has chest pain" is an answer, not a negated list
                return not (in_list and k + 1 < len(tokens) and tokens[k + 1] == COMMA)
            # "aisa kuch nahi ki khud ko nuksan ..." puts the negation before the symptom
            if t in self.neg_after and k + 1 < len(tokens) and tokens[k + 1] in ("ki", "ke"):
                return True
            item_len += 1
            if item_len >= (LIST_ITEM if in_list else NEG_WINDOW):
                return False
        return False

    def negate_or_lists(self, hits: list[Hit], tokens: list[str], english: bool = False) -> None:
        """"behoshi ya seene mein dard kuch nahi": a negation at the end of an "or" list covers
        the earlier items too. Works right to left so the negation runs back along the list."""
        joins = OR_WORDS | (OR_WORDS_EN if english else set())
        ordered = sorted(hits, key=lambda h: (h.start, h.end))
        for i in range(len(ordered) - 1, -1, -1):
            h = ordered[i]
            if h.negated or h.pattern.has_negation:
                continue
            later = [g for g in ordered if g.start >= h.end and g.start - h.end <= 6]
            if not later:
                continue
            first = min(g.start for g in later)
            if not any(g.negated for g in later if g.start == first):
                continue
            between = tokens[h.end:first]
            # "fever 1 or 2 days, no vomiting": the "or" joins two numbers, not two symptoms
            if any(t.isdigit() or t in COUNT_WORDS for t in between):
                continue
            if any(t in joins for t in between) and not any(
                    t == BOUNDARY or t in self.breakers or t in LIST_VERBS for t in between):
                h.negated = True

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

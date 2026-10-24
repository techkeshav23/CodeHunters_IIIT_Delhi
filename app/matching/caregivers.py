"""Caregiver profiles: loading, tolerant field mapping, and availability slots.

The organisers' file format is not known yet, so common key names are
accepted (id / caregiver_id, lat+lng at top level or under location, skills as
a list or a comma string, availability as ISO datetimes, ranges or daily
windows).
"""
from __future__ import annotations

import csv
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from .. import config

IST = timezone(timedelta(hours=5, minutes=30))
DEV_SAMPLE = config.DATA_DIR / "dev_caregivers.json"
log = logging.getLogger(__name__)


@dataclass
class Caregiver:
    id: str
    name: str
    role: str
    skills: list[str]
    languages: list[str]
    lat: float | None
    lng: float | None
    rating: float | None
    rating_count: int
    gender: str | None
    specialty: str | None
    area: str | None
    slots: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def now() -> datetime:
    if config.NOW_OVERRIDE:
        dt = datetime.fromisoformat(config.NOW_OVERRIDE)
        return dt if dt.tzinfo else dt.replace(tzinfo=IST)
    return datetime.now(IST)


def _decoded(value):
    """A CSV cell holding JSON ('["Hindi", "English"]') becomes the list or dict it spells."""
    if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _list(value) -> list[str]:
    value = _decoded(value)
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in re.split(r"[,;|/]", value) if v.strip()]
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out += _list(v) if isinstance(v, str) else [json.dumps(v) if isinstance(v, dict) else str(v)]
        return out
    return [str(value)]


def _first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _float(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def normalise(d: dict, index: int = 0) -> Caregiver:
    # "Caregiver ID", " role", "Lat-itude" -> caregiver_id, role, lat_itude
    d = {re.sub(r"[\s\-]+", "_", str(k).strip().lower()): v for k, v in d.items()}
    loc = _decoded(d.get("location"))
    loc = loc if isinstance(loc, dict) else {}
    slots = _decoded(_first(d, "availability", "availability_slots", "slots", "available_slots", default=[]))
    if isinstance(slots, str):
        slots = [s.strip() for s in re.split(r"[;|]", slots) if s.strip()]
    elif isinstance(slots, dict):  # {"start": ..., "end": ...}
        slots = [slots]
    slots = [json.dumps(s) if isinstance(s, dict) else str(s) for s in (slots or [])]
    return Caregiver(
        id=str(_first(d, "caregiver_id", "id", "cg_id", "caregiverId", default=f"CG_{index + 1:03d}")),
        name=str(_first(d, "name", "full_name", default="")),
        role=str(_first(d, "role", "type", "category", "designation", default="")).strip().lower(),
        skills=[s.lower() for s in _list(_first(d, "skills", "skill", "services", default=[]))],
        languages=[s.strip().title() for s in _list(_first(d, "languages", "language", "langs", default=[]))],
        lat=_float(_first(loc, "lat", "latitude", default=_first(d, "lat", "latitude"))),
        lng=_float(_first(loc, "lng", "lon", "long", "longitude", default=_first(d, "lng", "lon", "longitude"))),
        rating=_float(_first(d, "rating", "avg_rating", "stars")),
        rating_count=max(0, int(_float(_first(d, "rating_count", "reviews", "num_ratings", default=0)) or 0)),
        gender=(str(_first(d, "gender", "sex", default="")).lower() or None),
        specialty=(str(_first(d, "specialty", "specialisation", "specialization", "speciality", default="")).lower() or None),
        area=_first(loc, "area", "locality", default=_first(d, "area", "locality")),
        slots=slots,
        raw=d,
    )


def _read(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh, skipinitialspace=True))
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return _records(json.loads(text))


_RECORD_KEYS = {"role", "name", "skills", "caregiver_id", "id", "type", "designation", "languages"}


def _records(data, depth: int = 0) -> list[dict]:
    """The caregiver rows inside whatever wraps them: a list, {"caregivers": [...]},
    {"data": {"caregivers": [...]}}, or {"CG_001": {...}} keyed by id."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict) or depth > 3:
        return []
    named = [data[k] for k in ("caregivers", "caregiver_profiles", "profiles", "data", "items", "records") if k in data]
    for value in named + [v for v in data.values() if v not in named]:
        if isinstance(value, list) and any(isinstance(x, dict) for x in value):
            return value
    for value in named + [v for v in data.values() if v not in named]:
        if isinstance(value, dict):
            found = _records(value, depth + 1)
            if found:
                return found
    rows = [{"caregiver_id": k, **v} for k, v in data.items() if isinstance(v, dict) and _RECORD_KEYS & set(v)]
    return rows


def _load_rows(path: Path) -> list[Caregiver]:
    out = []
    for i, d in enumerate(_read(path)):
        if not isinstance(d, dict):
            continue
        try:
            out.append(normalise(d, i))
        except Exception as e:  # one bad row must not take the service down
            log.warning("skipping caregiver row %d in %s: %s", i, path, e)
    return out


def source_path() -> tuple[Path, str]:
    if config.CAREGIVERS_PATH:
        return Path(config.CAREGIVERS_PATH), "env"
    for name in ("caregivers.json", "caregiver_profiles.json", "caregivers.jsonl", "caregivers.csv",
                 "caregiver_profiles.csv"):
        p = config.PROVIDED_DIR / name
        if p.exists():
            return p, "provided"
    return DEV_SAMPLE, "dev_sample"


@lru_cache(maxsize=1)
def load() -> tuple[list[Caregiver], str]:
    """The caregiver pool and where it came from. An unreadable file falls back to
    the dev sample, and /health says so, instead of failing every request."""
    path, kind = source_path()
    try:
        rows = _load_rows(path)
        if path == DEV_SAMPLE or any(r.role for r in rows):
            return rows, kind
        error = "no caregiver rows with a role found"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    log.error("could not load caregivers from %s (%s); using the dev sample", path, error)
    return _load_rows(DEV_SAMPLE), f"dev_sample_fallback: {error}"[:200]


# ---- availability ---------------------------------------------------------
_TIME = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"


def _parse_time(text: str) -> time | None:
    m = re.fullmatch(_TIME, text.strip().lower())
    if not m:
        return None
    h, mnt, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    return time(h, mnt) if 0 <= h < 24 and 0 <= mnt < 60 else None


def _iso(text: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


def next_free(slots: list[str], ref: datetime) -> datetime | None:
    """Earliest start at or after `ref` across all slot strings."""
    best: datetime | None = None

    def offer(dt: datetime | None) -> None:
        nonlocal best
        if dt is not None and dt >= ref - timedelta(minutes=1) and (best is None or dt < best):
            best = dt

    def window(day: datetime, t0: time, t1: time | None) -> None:
        start = datetime.combine(day.date(), t0, IST)
        end = datetime.combine(day.date(), t1, IST) if t1 else None
        if start >= ref:
            offer(start)
        elif end and ref < end:
            # inside the window: next quarter hour
            q = ref + timedelta(minutes=(15 - ref.minute % 15) % 15)
            offer(q.replace(second=0, microsecond=0))

    for raw in slots:
        s = raw.strip()
        if s.startswith("{"):
            try:
                d = json.loads(s)
            except ValueError:
                continue
            s = str(_first(d, "start", "from", "slot", default=""))
            if "end" in d or "to" in d:
                s = f"{s}/{_first(d, 'end', 'to')}"
        low = s.lower()
        if "/" in s and _iso(s.split("/")[0]):
            a, b = (_iso(p) for p in s.split("/", 1))
            if a and b and a < ref < b:
                offer(ref.replace(second=0, microsecond=0))
            offer(a)
            continue
        dt = _iso(s)
        if dt:
            offer(dt)
            continue
        m = re.fullmatch(r"(today|tomorrow|daily|everyday|)\s*" + _TIME + r"(?:\s*-\s*" + _TIME + r")?", low)
        if not m:
            continue
        word = m.group(1)
        t0 = _parse_time(low[len(word):].split("-")[0])
        t1 = _parse_time(low.split("-")[1]) if "-" in low else None
        if t0 is None:
            continue
        if word in ("today", "tomorrow"):
            day = ref if word == "today" else ref + timedelta(days=1)
            window(day, t0, t1)
        else:  # daily window or a bare time: today, else tomorrow
            window(ref, t0, t1)
            window(ref + timedelta(days=1), t0, t1)
    return best

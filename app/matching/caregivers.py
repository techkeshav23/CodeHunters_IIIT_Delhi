"""Caregiver profiles: loading, tolerant field mapping, and availability slots.

The organisers' roster (data/sanocare_v1/caregivers.csv) has base_lat/base_lng,
max_radius_km, free_from/free_until (today's window, 24h IST), active, tier,
qualification, experience_years and `;`-separated languages and skills. Other
layouts still load: id / caregiver_id, lat+lng at top level or under location,
skills as a list or a comma string, availability as ISO datetimes, ranges or
daily windows.
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
    radius_km: float | None = None       # serves requests within this distance (home visits)
    free_from: str | None = None         # today's window, "HH:MM"
    free_until: str | None = None
    active: bool = True                  # inactive caregivers are never matched
    tier: str | None = None
    qualification: str | None = None
    experience_years: float | None = None

    @property
    def window(self) -> str | None:
        """Today's window as the organisers write it: "11:00–19:00"."""
        if self.free_from and self.free_until:
            return f"{self.free_from}–{self.free_until}"
        return None


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


_FALSE = {"false", "0", "no", "n", "inactive", "off", "disabled", "f"}
_GENDER = {"f": "female", "m": "male", "w": "female"}


def _bool(value, default: bool = True) -> bool:
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() not in _FALSE


def _clock(value) -> str | None:
    """"9:00", "09:00:00", "4 pm" -> "HH:MM"; anything else -> None."""
    if value is None:
        return None
    t = _parse_time(re.sub(r"^(\d{1,2}:\d{2}):\d{2}$", r"\1", str(value).strip()))
    return f"{t.hour:02d}:{t.minute:02d}" if t else None


def _text(value) -> str | None:
    s = str(value).strip() if value is not None else ""
    return s or None


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
    # the organisers' roster: one window today (free_from / free_until, 24h IST)
    free_from = _clock(_first(d, "free_from", "available_from", "shift_start", "start_time", "from_time"))
    free_until = _clock(_first(d, "free_until", "available_until", "free_to", "shift_end", "end_time", "to_time"))
    if free_from and not slots:
        slots = [f"today {free_from}-{free_until}" if free_until else f"today {free_from}"]
    gender = str(_first(d, "gender", "sex", default="")).strip().lower()
    radius = _float(_first(d, "max_radius_km", "radius_km", "service_radius_km", "max_radius", "radius"))
    return Caregiver(
        id=str(_first(d, "caregiver_id", "id", "cg_id", "caregiverid", default=f"CG_{index + 1:03d}")),
        name=str(_first(d, "name", "full_name", default="")),
        role=str(_first(d, "role", "type", "category", "designation", default="")).strip().lower(),
        skills=[s.lower() for s in _list(_first(d, "skills", "skill", "services", default=[]))],
        languages=[s.strip().title() for s in _list(_first(d, "languages", "language", "langs", default=[]))],
        lat=_float(_first(loc, "lat", "latitude", default=_first(d, "lat", "latitude", "base_lat", "base_latitude"))),
        lng=_float(_first(loc, "lng", "lon", "long", "longitude",
                          default=_first(d, "lng", "lon", "longitude", "base_lng", "base_lon", "base_longitude"))),
        rating=_float(_first(d, "rating", "avg_rating", "stars")),
        rating_count=max(0, int(_float(_first(d, "rating_count", "reviews", "num_ratings", default=0)) or 0)),
        gender=_GENDER.get(gender, gender) or None,
        specialty=(str(_first(d, "specialty", "specialisation", "specialization", "speciality", default="")).lower() or None),
        area=_first(loc, "area", "locality", default=_first(d, "area", "locality", "base_area")),
        slots=slots,
        raw=d,
        radius_km=radius if radius is not None and radius > 0 else None,
        free_from=free_from,
        free_until=free_until,
        active=_bool(_first(d, "active", "is_active", "enabled"), True)
        and str(d.get("status", "")).strip().lower() not in ("inactive", "disabled", "off"),
        tier=(_text(_first(d, "tier", "level")) or "").lower() or None,
        qualification=_text(_first(d, "qualification", "qualifications", "degree")),
        experience_years=_float(_first(d, "experience_years", "experience", "years_experience", "exp_years")),
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


ORG_ROSTER = config.ORG_DATA_DIR / "caregivers.csv"


def _sources() -> list[tuple[Path, str]]:
    """Candidate files, best first: env CC_CAREGIVERS, data/provided/, the organisers'
    roster (data/sanocare_v1), then the dev sample."""
    out: list[tuple[Path, str]] = []
    if config.CAREGIVERS_PATH:
        out.append((Path(config.CAREGIVERS_PATH), "env"))
    for name in ("caregivers.json", "caregiver_profiles.json", "caregivers.jsonl", "caregivers.csv",
                 "caregiver_profiles.csv"):
        p = config.PROVIDED_DIR / name
        if p.exists():
            out.append((p, "provided"))
            break
    if ORG_ROSTER.exists():
        out.append((ORG_ROSTER, "sanocare_v1"))
    out.append((DEV_SAMPLE, "dev_sample"))
    return out


def source_path() -> tuple[Path, str]:
    return _sources()[0]


@lru_cache(maxsize=1)
def load() -> tuple[list[Caregiver], str]:
    """The caregiver pool and where it came from. An unreadable file falls back to
    the next source (the organisers' roster, then the dev sample), and /health says
    so, instead of failing every request. Inactive caregivers stay in the pool (the
    roster view shows them); the ranker never matches them."""
    errors = []
    for path, kind in _sources():
        try:
            rows = _load_rows(path)
            if path == DEV_SAMPLE or any(r.role for r in rows):
                if errors:
                    log.error("could not load caregivers (%s); using %s", "; ".join(errors), path)
                    return rows, f"{kind}_fallback: {'; '.join(errors)}"[:200]
                return rows, kind
            errors.append(f"{path.name}: no caregiver rows with a role found")
        except Exception as e:
            errors.append(f"{path.name}: {type(e).__name__}: {e}")
    return [], f"none: {'; '.join(errors)}"[:200]


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

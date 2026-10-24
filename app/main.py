"""CareCompass API. Run: uvicorn app.main:app --port 8000"""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .matching.caregivers import IST, load
from .nlp.lexicon import get_lexicon
from .pipeline import run
from .schemas import Booking, BookingRequest, TriageRequest, TriageResponse, TriageResponseWithTrace
from .triage.model import get_model

app = FastAPI(
    title="CareCompass API",
    version=config.VERSION,
    description="Care navigation and caregiver matching for English, Hindi and Hinglish requests. "
                "Routing support only: no diagnosis, no prescriptions.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_BOOKINGS: dict[str, Booking] = {}


@app.on_event("startup")
def _warm() -> None:
    get_lexicon()
    load()
    get_model()


@app.get("/health")
def health() -> dict:
    caregivers, source = load()
    model = get_model()
    return {"status": "ok", "version": config.VERSION, "caregivers_source": source,
            "caregivers": len(caregivers),
            "model": "rules+model" if model else "rules",
            "model_trained_at": model.meta.get("trained_at") if model else None,
            "model_test_accuracy": (model.meta.get("scores", {}).get("test") or {}).get("accuracy") if model else None}


@app.post("/v1/triage", response_model=TriageResponseWithTrace | TriageResponse, response_model_exclude_none=False)
@app.post("/triage", response_model=TriageResponseWithTrace | TriageResponse, include_in_schema=False)
def triage(req: TriageRequest,
           explain: bool = Query(False, description="Add `trace` for the web app"),
           policy: str | None = Query(None, pattern="^(minimal|safety)$",
                                      description="Follow-up policy: minimal (default) or safety")):
    return run(req, mode="interactive", policy=policy, explain=explain)


@app.post("/v1/bookings", response_model=Booking, status_code=201)
def book(req: BookingRequest) -> Booking:
    caregivers, _ = load()
    cg = next((c for c in caregivers if c.id == req.caregiver_id), None)
    if cg is None:
        raise HTTPException(status_code=404, detail="Unknown caregiver_id")
    booking = Booking(booking_id="BK_" + secrets.token_hex(3).upper(), status="confirmed",
                      caregiver_id=cg.id, caregiver_name=cg.name, slot=req.slot,
                      created_at=datetime.now(IST).isoformat(timespec="seconds"))
    _BOOKINGS[booking.booking_id] = booking
    return booking


@app.get("/v1/bookings/{booking_id}", response_model=Booking)
def get_booking(booking_id: str) -> Booking:
    if booking_id not in _BOOKINGS:
        raise HTTPException(status_code=404, detail="Unknown booking_id")
    return _BOOKINGS[booking_id]


@app.get("/v1/labels")
def labels() -> dict:
    lex = get_lexicon()
    return {
        "care_types": config.CARE_TYPES,
        "urgency": config.URGENCY,
        "red_flags": [{"id": e.id, "label": e.label, "label_hinglish": e.label_hinglish, "label_hi": e.label_hi}
                      for e in lex.entries["red_flag"]],
        "emergency_numbers": config.EMERGENCY_NUMBERS,
        "helplines": config.FLAG_HELPLINES,
    }


@app.get("/v1/caregivers")
def caregivers() -> dict:
    items, source = load()
    return {"source": source, "caregivers": [c.raw for c in items]}

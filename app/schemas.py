"""Request and response models, following the indicative schema in the problem
statement. Swap field names here when the final schema is published."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class TriageRequest(BaseModel):
    # Extra fields are tolerated so an early client of the final schema still works.
    model_config = ConfigDict(extra="allow")

    user_input: str = Field(default="", max_length=4000)
    language: str = "auto"
    location: Location | None = None
    # Format not fixed yet: we accept strings, {"role", "content"},
    # {"question", "answer"} and similar dicts (see pipeline.read_history).
    conversation_history: list[str | dict[str, Any]] = Field(default_factory=list)


class MatchedCaregiver(BaseModel):
    caregiver_id: str
    score: float
    reason: str


class TriageResponse(BaseModel):
    follow_up_question: str | None = None
    care_type: str | None = None
    urgency: str | None = None
    red_flags: list[str] = Field(default_factory=list)
    reasoning: str = ""
    matched_caregivers: list[MatchedCaregiver] = Field(default_factory=list)


class TriageResponseWithTrace(TriageResponse):
    """Only returned with ?explain=true. The UI uses `trace` for the
    "what we understood" and "why" panels."""

    trace: dict[str, Any] = Field(default_factory=dict)


class BookingRequest(BaseModel):
    caregiver_id: str
    slot: str | None = None
    care_type: str | None = None
    urgency: str | None = None
    note: str | None = Field(default=None, max_length=500)


class Booking(BaseModel):
    booking_id: str
    status: str
    caregiver_id: str
    caregiver_name: str | None = None
    slot: str | None = None
    created_at: str

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.calendar import EventCategory
from app.schemas.common import OrmBase


class CalendarEventDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    title: str
    description: str | None
    start_at: str
    end_at: str | None
    all_day: bool
    provider: str | None
    location: str | None
    purpose: str | None
    source: str
    status: str
    category: str
    created_at: datetime


class CalendarEventCreateRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    title: str
    description: str | None = None
    start_at: str
    end_at: str | None = None
    all_day: bool = False
    provider: str | None = None
    location: str | None = None
    purpose: str | None = None
    # One vocabulary for every category, labelled per category in the UI: at a
    # deadline `done`/`cancelled` read as "Widerspruch eingelegt"/"Kein Widerspruch",
    # at an appointment as done/cancelled. Anything but `scheduled` also silences the
    # reminders, which is the point: nagging about a deadline already acted on burns
    # the credibility of every later reminder.
    status: Literal["scheduled", "done", "cancelled"] = "scheduled"
    category: EventCategory = EventCategory.appointment


class CalendarEventUpdateRequest(CalendarEventCreateRequest):
    title: str | None = None
    start_at: str | None = None
    category: EventCategory | None = None


class CalendarFeedItem(BaseModel):
    id: uuid.UUID
    title: str
    start: str
    end: str | None
    all_day: bool
    type: str
    color: str
    url: str | None = None
    # documents: the class slug (lab_report, doctor_letter, …) so the client can
    # show "Arztbrief · Diak Klinikum" instead of img20240405_08273634.pdf
    classification: str | None = None


class CalendarFeedDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    created_at: datetime
    revoked_at: datetime | None
    last_accessed_at: datetime | None


class CalendarFeedCreatedDto(CalendarFeedDto):
    # The plaintext token is shown once, here, and never again — only its hash persists.
    url: str

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import OrmBase
from app.schemas.dose import GIVEN_AT


class IncidentIn(BaseModel):
    incident_type: Literal["seizure", "fall", "allergic_reaction", "other"]
    incident_type_display: str | None = Field(None, max_length=256)
    occurred_at: str = Field(pattern=GIVEN_AT)  # local wall time (ADR 062)
    duration_minutes: int | None = Field(None, ge=0, le=100000)
    actions_taken: str | None = Field(None, max_length=10000)
    note: str | None = Field(None, max_length=10000)


class IncidentDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    incident_type: str
    incident_type_display: str | None
    occurred_at: str
    duration_minutes: int | None
    actions_taken: str | None
    note: str | None
    entered_by: str
    can_edit: bool

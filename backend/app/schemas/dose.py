import uuid

from pydantic import BaseModel, Field

from app.schemas.common import OrmBase

GIVEN_AT = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"


class DoseIn(BaseModel):
    medication_id: uuid.UUID
    given_at: str = Field(pattern=GIVEN_AT)  # local wall time (ADR 060)
    given_by: str | None = Field(None, max_length=256)
    amount: str | None = Field(None, max_length=256)
    note: str | None = Field(None, max_length=10000)
    incident_id: uuid.UUID | None = None


class DoseDto(OrmBase):
    id: uuid.UUID
    medication_id: uuid.UUID
    given_at: str
    given_by: str | None
    amount: str | None
    note: str | None
    incident_id: uuid.UUID | None
    entered_by: str
    can_edit: bool

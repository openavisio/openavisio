import uuid

from pydantic import BaseModel, Field

from app.schemas.document import DocumentDto
from app.schemas.medication import MedicationDto


class StepIn(BaseModel):
    text: str = Field(max_length=2000)
    medication_id: uuid.UUID | None = None


class SituationIn(BaseModel):
    trigger: str = Field(max_length=500)
    steps: list[StepIn] = Field(default_factory=list, max_length=50)


class ContactIn(BaseModel):
    name: str = Field(max_length=256)
    role: str | None = Field(None, max_length=256)
    phone: str | None = Field(None, max_length=64)


class EmergencyPlanIn(BaseModel):
    situations: list[SituationIn] = Field(default_factory=list, max_length=50)
    contacts: list[ContactIn] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(None, max_length=10000)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class StepDto(StepIn):
    # None with medication_id set: the Medication was deleted
    medication: MedicationDto | None = None


class SituationDto(SituationIn):
    steps: list[StepDto]


class EmergencyPlanDto(BaseModel):
    situations: list[SituationDto]
    contacts: list[ContactIn]
    notes: str | None
    documents: list[DocumentDto]

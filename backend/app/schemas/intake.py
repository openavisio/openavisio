import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmBase

Aging = Literal["lasting", "changeable", "visit_only"]


class IntakeFormDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    title: str | None
    file_name: str | None
    status: str
    processing_error: str | None
    created_at: datetime
    released_at: datetime | None


class IntakeSourceDto(BaseModel):
    text: str
    segment: str | None


class IntakeDocumentDto(BaseModel):
    id: uuid.UUID
    file_name: str


class IntakeItemDto(BaseModel):
    text: str
    section: str | None
    kind: Literal["fact", "judgement"]
    aging: Aging
    answer: str | None
    origin: Literal["record", "history", "document", "caregiver"] | None
    sources: list[IntakeSourceDto]
    related: list[str]
    fact_id: uuid.UUID | None
    document: IntakeDocumentDto | None
    passage: str | None
    confirmed: bool
    record_corrected: bool


class IntakeFormDetailDto(IntakeFormDto):
    items: list[IntakeItemDto] = []


class IntakeItemIn(BaseModel):
    """`answer` sent (even null) is an answer; left out, only aging/confirm apply."""
    answer: str | None = Field(None, max_length=5000)
    aging: Aging | None = None
    confirm: bool = False


class HistoryFactDto(OrmBase):
    id: uuid.UUID
    question: str
    answer: str
    aging: Aging
    confirmed_on: str
    source: str
    document_reference_id: uuid.UUID | None
    intake_form_id: uuid.UUID | None


class HistoryFactIn(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)
    aging: Aging

    @field_validator("answer")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer is blank")
        return v.strip()

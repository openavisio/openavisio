import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class ConditionSourceDto(OrmBase):
    document_reference_id: uuid.UUID
    issued_date: str | None
    label: str | None
    doc_type: str | None


class ConditionDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    clinical_status: str
    verification_status: str | None
    category: str | None
    severity: str | None
    code: str | None
    code_display: str
    recorded_date: str | None
    onset_date_time: str | None
    abatement_date_time: str | None
    note: str | None
    document_reference_id: uuid.UUID | None
    created_at: datetime
    sources: list[ConditionSourceDto] = []


class ConditionMergeRequest(BaseModel):
    other_id: uuid.UUID


class ConditionCreateRequest(BaseModel):
    clinical_status: str = "active"
    verification_status: str | None = None
    category: str | None = None
    severity: str | None = None
    code: str | None = None
    code_display: str
    recorded_date: str | None = None
    onset_date_time: str | None = None
    abatement_date_time: str | None = None
    note: str | None = None


class ConditionUpdateRequest(ConditionCreateRequest):
    code_display: str | None = None

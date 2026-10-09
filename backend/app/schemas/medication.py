import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class MedicationDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    medication_code: str | None
    medication_display: str
    date_asserted: str | None
    effective_start: str | None
    effective_end: str | None
    dosage_text: str | None
    dose_quantity: float | None
    dose_unit: str | None
    route: str | None
    reason_code: str | None
    note: str | None
    document_reference_id: uuid.UUID | None
    created_at: datetime
    is_active: bool = True


class MedicationCreateRequest(BaseModel):
    status: str = "active"
    medication_code: str | None = None
    medication_display: str
    date_asserted: str | None = None
    effective_start: str | None = None
    effective_end: str | None = None
    dosage_text: str | None = None
    dose_quantity: float | None = None
    dose_unit: str | None = None
    route: str | None = None
    reason_code: str | None = None
    note: str | None = None


class MedicationUpdateRequest(MedicationCreateRequest):
    medication_display: str | None = None

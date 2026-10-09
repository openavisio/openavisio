import uuid

from pydantic import BaseModel

from app.schemas.common import OrmBase


class ObservationDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    code: str | None
    code_display: str | None
    category: str | None
    panel: str | None
    effective_date_time: str | None
    value_quantity: float | None
    value_unit: str | None
    value_string: str | None
    reference_range: str | None
    ref_low: float | None
    ref_high: float | None
    document_reference_id: uuid.UUID | None


class ObservationCreateRequest(BaseModel):
    status: str = "final"
    code: str | None = None
    code_display: str | None = None
    category: str | None = None
    panel: str | None = None
    effective_date_time: str | None = None
    value_quantity: float | None = None
    value_unit: str | None = None
    value_string: str | None = None
    reference_range: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None

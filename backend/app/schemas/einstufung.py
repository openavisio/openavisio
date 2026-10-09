import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OrmBase


class EinstufungDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    pflegegrad: int | None
    total_points: float | None
    valid_from: str | None
    valid_until: str | None
    note: str | None
    authority: str | None
    file_reference: str | None
    module_mobility: float | None
    module_cognitive: float | None
    module_behaviour: float | None
    module_self_care: float | None
    module_therapy_demands: float | None
    module_daily_life: float | None
    source: str
    document_reference_id: uuid.UUID | None
    created_at: datetime


class EinstufungCreateRequest(BaseModel):
    # 1..5 is the whole scale; anything else is a typo or a misread table.
    pflegegrad: int | None = Field(None, ge=1, le=5)
    # 0..100 by construction: the modules are weighted to sum to a hundred.
    total_points: float | None = Field(None, ge=0, le=100)
    valid_from: str | None = None
    valid_until: str | None = None
    note: str | None = None
    authority: str | None = None
    file_reference: str | None = None
    module_mobility: float | None = Field(None, ge=0, le=10)
    module_cognitive: float | None = Field(None, ge=0, le=15)
    module_behaviour: float | None = Field(None, ge=0, le=15)
    module_self_care: float | None = Field(None, ge=0, le=40)
    module_therapy_demands: float | None = Field(None, ge=0, le=20)
    module_daily_life: float | None = Field(None, ge=0, le=15)
    document_reference_id: uuid.UUID | None = None


class EinstufungUpdateRequest(EinstufungCreateRequest):
    pass


class ScaleThreshold(BaseModel):
    from_: float = Field(alias="from")
    to: float
    grade: int

    model_config = {"populate_by_name": True}


class EinstufungScaleDto(BaseModel):
    """Where the current total sits between the statutory thresholds.

    A position, not a distance: "5 points to Pflegegrad 3" reads like a target to
    aim for, and points come out of an assessment of actual need (ADR 042).
    """

    total: float
    grade: int | None
    thresholds: list[ScaleThreshold]

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class DiaryEntryDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    subject: str | None
    entry_date: str
    entry_time: str | None
    mood: int | None
    pain_level: int | None
    mobility: int | None
    sleep_hours: float | None
    sleep_quality: int | None
    nutrition_notes: str | None
    bowel_movement: bool | None
    medication_compliance: bool | None
    general_notes: str | None
    custom_fields: dict | None
    created_at: datetime


class DiaryEntryCreateRequest(BaseModel):
    entry_date: str
    entry_time: str | None = None
    subject: str | None = None
    mood: int | None = None
    pain_level: int | None = None
    mobility: int | None = None
    sleep_hours: float | None = None
    sleep_quality: int | None = None
    nutrition_notes: str | None = None
    bowel_movement: bool | None = None
    medication_compliance: bool | None = None
    general_notes: str | None = None
    custom_fields: dict | None = None


class DiaryEntryUpdateRequest(DiaryEntryCreateRequest):
    entry_date: str | None = None


class DiaryTemplateDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID | None
    name: str
    fields: list
    is_default: bool


class DiaryTemplateCreateRequest(BaseModel):
    name: str
    fields: list = []
    is_default: bool = False


class DiaryTemplateUpdateRequest(BaseModel):
    name: str | None = None
    fields: list | None = None
    is_default: bool | None = None

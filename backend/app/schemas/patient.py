import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class PatientDto(OrmBase):
    id: uuid.UUID
    given_name: str
    family_name: str
    birth_date: str | None
    gender: str | None
    active: bool
    identifier: str | None
    created_at: datetime
    is_favorite: bool = False
    has_photo: bool = False


class PatientCreateRequest(BaseModel):
    given_name: str
    family_name: str
    birth_date: str | None = None
    gender: str | None = None
    identifier: str | None = None


class PatientUpdateRequest(BaseModel):
    given_name: str | None = None
    family_name: str | None = None
    birth_date: str | None = None
    gender: str | None = None
    active: bool | None = None
    identifier: str | None = None

import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmBase


class CarerUpdateIn(BaseModel):
    correspondent_id: uuid.UUID
    person: str | None = Field(None, max_length=256)
    day: date
    text: str = Field(min_length=1, max_length=10000)
    retold: bool = False

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v.strip()


class CarerUpdateDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    correspondent_id: uuid.UUID
    correspondent_name: str
    person: str | None
    day: str
    text: str
    retold: bool

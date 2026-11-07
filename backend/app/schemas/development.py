import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmBase

Domain = Literal["communication", "daily_living", "social", "motor", "learning"]
Place = Literal["home", "kita_school", "therapy", "out"]


def _month_or_day(v: str) -> str:
    # a month is enough when filling in after the fact (ADR 063)
    try:
        date.fromisoformat(v if len(v) == 10 else f"{v}-01")
    except ValueError:
        raise ValueError("expected YYYY-MM or YYYY-MM-DD") from None
    if len(v) not in (7, 10):
        raise ValueError("expected YYYY-MM or YYYY-MM-DD")
    return v


def _clean_name(v: str) -> str:
    if not v.strip():
        raise ValueError("name is blank")
    return " ".join(v.split())


class AbilityObservationIn(BaseModel):
    ability_name: str = Field(min_length=1, max_length=256)  # an existing name joins that Ability
    domain: Domain | None = None  # only used when the name starts a new Ability
    observed_on: str
    place: Place | None = None
    works: bool
    with_help: bool = False
    note: str | None = Field(None, max_length=10000)

    _date = field_validator("observed_on")(_month_or_day)
    _name = field_validator("ability_name")(_clean_name)


class AbilityIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    domain: Domain | None = None

    _name = field_validator("name")(_clean_name)


class AbilityObservationDto(OrmBase):
    id: uuid.UUID
    ability_id: uuid.UUID
    observed_on: str
    place: str | None
    works: bool
    with_help: bool
    no_longer: bool
    note: str | None
    source: str
    document_id: uuid.UUID | None
    entered_by: str
    can_edit: bool


class AbilityDto(OrmBase):
    id: uuid.UUID
    name: str
    domain: str | None
    can_edit: bool
    observations: list[AbilityObservationDto]  # oldest first; the last one is where it stands


class TestAttemptIn(BaseModel):
    test_name: str = Field(min_length=1, max_length=256)
    attempted_on: str
    correspondent_id: uuid.UUID | None = None
    setting: Literal["clinic", "practice", "home", "kita_school"] | None = None
    duration_minutes: int | None = Field(None, ge=0, le=100000)
    outcome: Literal["completed", "stopped", "refused", "not_attempted"]
    reason: str | None = Field(None, max_length=10000)
    document_id: uuid.UUID | None = None

    _date = field_validator("attempted_on")(_month_or_day)
    _test_name = field_validator("test_name")(_clean_name)


class TestAttemptDto(OrmBase):
    id: uuid.UUID
    test_name: str
    attempted_on: str
    correspondent_id: uuid.UUID | None
    correspondent_name: str | None
    setting: str | None
    duration_minutes: int | None
    outcome: str
    reason: str | None
    document_id: uuid.UUID | None
    medications: list[str]  # read from the record for that day, never entered
    entered_by: str
    can_edit: bool

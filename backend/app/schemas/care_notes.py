from pydantic import BaseModel, Field

from app.schemas.common import OrmBase


class CareNotesIn(BaseModel):
    communication: str | None = Field(None, max_length=5000)
    eating_drinking: str | None = Field(None, max_length=5000)
    sleep: str | None = Field(None, max_length=5000)
    aids: str | None = Field(None, max_length=5000)
    what_helps: str | None = Field(None, max_length=5000)
    what_overwhelms: str | None = Field(None, max_length=5000)


class CareNotesDto(CareNotesIn, OrmBase):
    pass

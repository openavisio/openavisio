import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PagedResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

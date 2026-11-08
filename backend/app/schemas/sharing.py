import uuid
from datetime import date, datetime

from typing import Any

from pydantic import BaseModel, field_validator

from app.models.sharing import DataSet, IdentificationMode
from app.schemas.development import Domain
from app.schemas.common import OrmBase


class SharingPurposeDto(OrmBase):
    id: uuid.UUID
    name: str
    description: str | None
    identification_mode: str
    status: str
    expires_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    created_by_user_id: uuid.UUID | None
    data_set: str | None
    data_set_since: str | None
    data_set_domain: str | None
    # Computed
    share_count: int = 0


class SharingPurposeCreateRequest(BaseModel):
    name: str
    description: str | None = None
    identification_mode: IdentificationMode = IdentificationMode.identified
    expires_at: datetime | None = None
    data_set: DataSet | None = None
    data_set_since: date | None = None
    data_set_domain: Domain | None = None

    @field_validator("data_set_domain")
    @classmethod
    def _domain_needs_observations(cls, v, info):
        if v and info.data.get("data_set") != DataSet.ability_observations:
            raise ValueError("a domain only filters Ability Observations")
        return v


class SharingPurposeUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    identification_mode: IdentificationMode | None = None
    expires_at: datetime | None = None


class OpenRequestDto(OrmBase):
    """A Sharing Purpose surfaced as an open request for a specific Patient."""

    id: uuid.UUID
    name: str
    description: str | None
    identification_mode: str
    expires_at: datetime | None
    created_at: datetime
    data_set: str | None
    data_set_since: str | None
    data_set_domain: str | None


class ShareDto(OrmBase):
    """A Patient-side view of a Share, for the Caregiver managing consent."""

    id: uuid.UUID
    sharing_purpose_id: uuid.UUID
    document_id: uuid.UUID | None
    patient_id: uuid.UUID
    status: str
    consented_at: datetime
    consented_legal: bool
    revoked_at: datetime | None
    # Computed
    purpose_name: str | None = None
    document_file_name: str | None = None
    data_set: str | None = None
    row_count: int | None = None
    purpose_open: bool = False
    identification_mode: str | None = None


class ConsentRequest(BaseModel):
    document_ids: list[uuid.UUID] = []
    record_ids: list[uuid.UUID] = []  # Data Set rows the Caregiver left ticked


class DataSetRowDto(BaseModel):
    """One row as it would leave: the record id to pick it, the columns as frozen (ADR 064)."""

    id: uuid.UUID
    values: dict[str, Any]


class CollectedShareDto(BaseModel):
    """A Purpose-Manager-side view of a shared file in the collection screen."""

    share_id: uuid.UUID
    document_id: uuid.UUID | None
    row_count: int | None = None
    file_name: str | None
    content_type: str | None
    size: int | None
    consented_at: datetime
    patient_label: str
    patient_id: uuid.UUID | None  # None in anonymous mode

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.sharing import IdentificationMode
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
    # Computed
    share_count: int = 0


class SharingPurposeCreateRequest(BaseModel):
    name: str
    description: str | None = None
    identification_mode: IdentificationMode = IdentificationMode.identified
    expires_at: datetime | None = None


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


class ShareDto(OrmBase):
    """A Patient-side view of a Share, for the Caregiver managing consent."""

    id: uuid.UUID
    sharing_purpose_id: uuid.UUID
    document_id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    consented_at: datetime
    consented_legal: bool
    revoked_at: datetime | None
    # Computed
    purpose_name: str | None = None
    document_file_name: str | None = None


class ConsentRequest(BaseModel):
    document_ids: list[uuid.UUID]


class CollectedShareDto(BaseModel):
    """A Purpose-Manager-side view of a shared file in the collection screen."""

    share_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str | None
    content_type: str | None
    size: int | None
    consented_at: datetime
    patient_label: str
    patient_id: uuid.UUID | None  # None in anonymous mode

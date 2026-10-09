import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.common import OrmBase, PagedResult


class AdminUserDto(OrmBase):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class UpdateUserRoleRequest(BaseModel):
    role: str


class SetUserActiveRequest(BaseModel):
    is_active: bool


class InvitationDto(OrmBase):
    id: uuid.UUID
    email: str
    token: str
    expires_at: datetime
    is_used: bool
    created_at: datetime


class CreateInvitationRequest(BaseModel):
    email: EmailStr


class AdminGroupDto(OrmBase):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime


class AdminGroupMemberDto(OrmBase):
    id: uuid.UUID
    group_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str


class OllamaModelInfo(BaseModel):
    name: str
    size: int | None = None
    digest: str | None = None
    modified_at: str | None = None
    tasks: list[str] = []
    hint: str | None = None
    tags: list[str] = []


class OllamaSettingsDto(BaseModel):
    backend: str
    backend_type: str | None = None
    connected: bool
    url: str | None
    models: list[OllamaModelInfo]
    embed_model: str | None
    classify_model: str | None
    extract_model: str | None
    vision_model: str | None
    chat_model: str | None
    current_models: dict[str, str | None] = {}


class AiModelConfigRequest(BaseModel):
    extract_model: str | None = None
    classify_model: str | None = None
    chat_model: str | None = None
    vision_model: str | None = None


class OllamaPullRequest(BaseModel):
    model: str


class OllamaConnectionTestResult(BaseModel):
    success: bool
    message: str


class OllamaPullStatus(BaseModel):
    status: str
    progress: float | None = None


class AuditLogDto(OrmBase):
    id: uuid.UUID
    timestamp: datetime
    user_id: uuid.UUID | None
    user_name: str | None
    entity_type: str
    entity_id: str | None
    action: str
    changes: dict | None
    ip_address: str | None


class PipelineTaskDto(BaseModel):
    id: uuid.UUID
    file_name: str | None
    patient_name: str
    processing_status: str
    pipeline_stage: str | None
    processing_error: str | None
    updated_at: datetime


class TaskRunDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: str
    task_name: str
    args_summary: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime


class DataCategoryDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    is_builtin: bool
    lawful_basis: str | None
    retention_days: int | None


class UpdateDataCategoryRequest(BaseModel):
    lawful_basis: str | None = None
    retention_days: int | None = None


class LicenseDto(BaseModel):
    tier: str
    has_license: bool
    is_grace_period: bool
    issued_to: str | None
    expires_at: datetime | None
    grace_ends_at: datetime | None


class UploadLicenseRequest(BaseModel):
    token: str

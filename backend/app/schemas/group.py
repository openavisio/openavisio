import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

from app.schemas.common import OrmBase


class GroupDto(OrmBase):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime


class GroupCreateRequest(BaseModel):
    name: str


class GroupUpdateRequest(BaseModel):
    name: str


class GroupMemberDto(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    role: str
    status: str
    invited_at: datetime | None
    accepted_at: datetime | None


class GroupInviteInfoDto(BaseModel):
    group_id: uuid.UUID
    group_name: str


GroupRole = Literal["viewer", "manager", "owner"]


class GroupInviteRequest(BaseModel):
    email: EmailStr
    role: GroupRole = "viewer"


class GroupInviteResult(BaseModel):
    token: str
    invite_url: str


class UpdateMemberRoleRequest(BaseModel):
    role: GroupRole


class AssignPatientToGroupRequest(BaseModel):
    group_id: uuid.UUID


class GroupPatientDto(BaseModel):
    id: uuid.UUID
    given_name: str
    family_name: str

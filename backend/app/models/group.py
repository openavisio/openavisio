import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Group(BaseModel):
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    members: Mapped[list["GroupMembership"]] = relationship("GroupMembership", back_populates="group", lazy="select")
    patients: Mapped[list["Patient"]] = relationship("Patient", back_populates="group", foreign_keys="Patient.group_id", lazy="select")  # noqa: F821
    invite_tokens: Mapped[list["GroupInviteToken"]] = relationship("GroupInviteToken", back_populates="group", lazy="select")


class GroupMembership(BaseModel):
    __tablename__ = "group_memberships"

    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), default="viewer")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[Group] = relationship("Group", back_populates="members")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="group_memberships")  # noqa: F821


class GroupInviteToken(BaseModel):
    __tablename__ = "group_invite_tokens"

    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(256))
    token: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(default=False)

    group: Mapped[Group] = relationship("Group", back_populates="invite_tokens")

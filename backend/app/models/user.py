from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class UserRole(StrEnum):
    admin = "admin"
    manager = "manager"
    user = "user"


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # ADR 044: the only way back in when the password and the passkey device are
    # both gone. Shown once at setup, single use.
    recovery_code_hash: Mapped[str | None] = mapped_column(String(256))

    # Relationships
    passkey_credentials: Mapped[list["PasskeyCredential"]] = relationship(  # noqa: F821
        "PasskeyCredential", back_populates="user"
    )
    group_memberships: Mapped[list["GroupMembership"]] = relationship(  # noqa: F821
        "GroupMembership", foreign_keys="GroupMembership.user_id", back_populates="user"
    )

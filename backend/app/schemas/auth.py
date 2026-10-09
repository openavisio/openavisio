from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: str
    email: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ProfileResponse(BaseModel):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    last_login_at: str | None


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None


class InviteInfoResponse(BaseModel):
    email: str


class RegisterRequest(BaseModel):
    token: str
    first_name: str
    last_name: str
    password: str
    consent: bool = False  # GDPR onboarding consent (#15)


class RecoverRequest(BaseModel):
    """ADR 044: back in with the code from the setup sheet, nothing else."""

    email: EmailStr
    recovery_code: str
    new_password: str = Field(min_length=8)


class RecoverResponse(BaseModel):
    # The used code is spent, so a fresh one comes back with the answer.
    recovery_code: str

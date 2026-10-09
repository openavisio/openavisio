import uuid

from pydantic import BaseModel

from app.schemas.common import OrmBase


class OrganizationDto(OrmBase):
    id: uuid.UUID
    name: str
    description: str | None
    default_language: str = "en"
    legal_name: str | None = None
    legal_street: str | None = None
    legal_postcode: str | None = None
    legal_city: str | None = None
    legal_country: str | None = None
    legal_email: str | None = None
    legal_phone: str | None = None
    legal_responsible: str | None = None
    legal_vat_id: str | None = None
    legal_register: str | None = None
    dpo_contact: str | None = None
    is_household: bool = False


class OrganizationInitResponse(OrganizationDto):
    """The recovery code exists only in this one response (ADR 044)."""

    recovery_code: str


class SmtpConfig(BaseModel):
    host: str
    port: int = 587
    user: str | None = None
    password: str | None = None
    from_address: str | None = None


class AiConfig(BaseModel):
    backend: str  # mock | ollama | vllm
    url: str | None = None
    model: str | None = None
    api_key: str | None = None


class FirstPatientConfig(BaseModel):
    given_name: str
    family_name: str
    birth_date: str | None = None


class OrganizationInitRequest(BaseModel):
    name: str
    description: str | None = None
    locale: str = "en"
    admin_email: str
    admin_password: str
    admin_first_name: str | None = None
    admin_last_name: str | None = None
    smtp: SmtpConfig | None = None
    ai: AiConfig | None = None
    first_patient: FirstPatientConfig | None = None
    is_household: bool = False  # ADR 046


class OrganizationUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    default_language: str | None = None
    legal_name: str | None = None
    legal_street: str | None = None
    legal_postcode: str | None = None
    legal_city: str | None = None
    legal_country: str | None = None
    legal_email: str | None = None
    legal_phone: str | None = None
    legal_responsible: str | None = None
    legal_vat_id: str | None = None
    legal_register: str | None = None
    dpo_contact: str | None = None
    is_household: bool | None = None  # ADR 046

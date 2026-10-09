import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class CorrespondentDto(OrmBase):
    id: uuid.UUID
    name: str


class DocumentInsightsDto(BaseModel):
    """What a document contains — descriptive only, never evaluative (see doc_insights)."""
    summary: str | None = None
    provider: str | None = None
    observations: int = 0
    medications: int = 0
    diagnoses: int = 0
    recommendations: int = 0


class DocumentDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    type: str | None
    description: str | None
    issued_date: date | None
    file_name: str | None
    content_type: str | None
    size: int | None
    processing_status: str
    pipeline_stage: str | None
    verification_status: str
    document_classification: str | None
    detected_provider: str | None
    correspondent: CorrespondentDto | None = None
    insights: DocumentInsightsDto | None = None
    is_favorite: bool = False
    created_at: datetime


class ExtractionSummary(BaseModel):
    summary: str | None = None
    mentioned_persons: list[dict] = []
    observations: list[dict] = []
    diagnoses: list[dict] = []
    medications: list[dict] = []
    appointments: list[dict] = []
    recommendations: list[str] = []
    expenses: list[dict] = []


class DocumentDetailDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    type: str | None
    description: str | None
    issued_date: date | None
    file_name: str | None
    processing_status: str
    pipeline_stage: str | None
    processing_error: str | None
    verification_status: str
    document_classification: str | None
    detected_provider: str | None
    correspondent: CorrespondentDto | None = None
    extracted_text: str | None
    ocr_confidence: float | None
    extraction_confidence: float | None
    extraction_json: dict | None
    created_at: datetime


class UpdateDocumentRequest(BaseModel):
    issued_date: date | None = None
    description: str | None = None
    type: str | None = None
    correspondent_id: uuid.UUID | None = None


class VerifyDocumentRequest(BaseModel):
    observations: list[dict] = []
    diagnoses: list[dict] = []
    medications: list[dict] = []
    appointments: list[dict] = []
    recommendations: list[str] = []
    expenses: list[dict] = []
    decision: dict | None = None  # Kassenbescheid -> Widerspruch deadline (ADR 041)

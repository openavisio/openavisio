import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class IncidentDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    incident_type: str
    incident_type_display: str | None
    severity: str
    status: str
    occurred_at: str
    duration_minutes: int | None
    resolved_at: str | None
    location: str | None
    suspected_trigger: str | None
    symptoms: str | None
    actions_taken: str | None
    outcome: str | None
    note: str | None
    reported_to_provider: bool
    created_at: datetime


class IncidentCreateRequest(BaseModel):
    incident_type: str
    incident_type_display: str | None = None
    severity: str = "mild"
    occurred_at: str
    duration_minutes: int | None = None
    location: str | None = None
    suspected_trigger: str | None = None
    symptoms: str | None = None
    actions_taken: str | None = None
    outcome: str | None = None
    note: str | None = None
    weather_condition: str | None = None
    temperature: float | None = None
    humidity: float | None = None
    pollen_level: str | None = None
    air_quality_index: int | None = None
    activity_at_time: str | None = None
    hours_since_last_meal: float | None = None
    sleep_hours_previous_night: float | None = None
    reported_to_provider: bool = False


class IncidentUpdateRequest(IncidentCreateRequest):
    incident_type: str | None = None
    occurred_at: str | None = None
    status: str | None = None
    resolved_at: str | None = None


class IncidentSummaryDto(BaseModel):
    total_count: int
    last_30_days: int
    count_by_type: dict[str, int]
    count_by_severity: dict[str, int]
    most_common_type: str | None
    most_common_trigger: str | None

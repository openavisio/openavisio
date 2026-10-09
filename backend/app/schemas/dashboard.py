from pydantic import BaseModel


class ObservationDataPointDto(BaseModel):
    date: str
    value: float | None


class ObservationTrendDto(BaseModel):
    code: str
    display: str
    unit: str | None
    data_points: list[ObservationDataPointDto]


class MedicationTimelineDto(BaseModel):
    id: str
    display: str
    status: str
    start: str | None
    end: str | None


class IncidentFrequencyDto(BaseModel):
    type: str
    count: int


class ConditionTimelineDto(BaseModel):
    id: str
    display: str
    status: str
    onset: str | None
    severity: str | None


class PatientDashboardDto(BaseModel):
    observation_trends: list[ObservationTrendDto] = []
    medication_timeline: list[MedicationTimelineDto] = []
    incident_frequency: list[IncidentFrequencyDto] = []
    total_documents: int = 0
    verified_documents: int = 0
    condition_timeline: list[ConditionTimelineDto] = []

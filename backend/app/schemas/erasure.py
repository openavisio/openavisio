from pydantic import BaseModel


class ErasePatientRequest(BaseModel):
    confirm_name: str  # must match "{given_name} {family_name}"


class EraseUserRequest(BaseModel):
    confirm_email: str  # must match the user's current email

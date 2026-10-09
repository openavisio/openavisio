from pydantic import BaseModel


class PasskeyCredentialResponse(BaseModel):
    id: str
    label: str
    aaguid: str | None
    created_at: str
    last_used_at: str | None


class PasskeyRegisterCompleteRequest(BaseModel):
    credential: dict
    expected_challenge: str
    label: str


class PasskeyAuthenticateCompleteRequest(BaseModel):
    credential: dict
    expected_challenge: str


class PasskeyRenameRequest(BaseModel):
    label: str

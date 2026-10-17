from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str


class ChatMessageDto(BaseModel):
    role: str
    content: str
    timestamp: datetime
    emergency_plan: bool = False


# docs/regulatory-positioning.md claimed "a clear disclaimer states it does not
# replace professional medical judgement" — and no such disclaimer existed
# anywhere in the code (#117). A guardrail that lives only in a document is worse
# than none, because it makes us believe we are covered. It ships with every
# answer now, so a client cannot quietly drop it.
CHAT_DISCLAIMER = (
    "Diese Antwort gibt wieder, was in deinen Dokumenten steht. Sie ist keine "
    "medizinische Beratung, keine Einschätzung und ersetzt kein ärztliches Urteil. "
    "Wende dich mit Fragen zu Befunden und Behandlung an die behandelnden "
    "Ärztinnen und Ärzte."
)


class ChatSourceDto(BaseModel):
    """A document the retrieval actually searched — not proof it was relevant (ADR 038)."""
    document_id: str
    file_name: str


class ChatResponse(BaseModel):
    answer: str
    history: list[ChatMessageDto]
    disclaimer: str = CHAT_DISCLAIMER
    sources: list[ChatSourceDto] = []
    # months (YYYY-MM) that hold calendar entries; a date link into an empty
    # month teaches the reader to stop clicking links (ADR 038)
    months: list[str] = []
    # ADR 048: the client shows a link to the Emergency Plan page
    emergency_plan: bool = False


class ChatHistoryDto(BaseModel):
    messages: list[ChatMessageDto]

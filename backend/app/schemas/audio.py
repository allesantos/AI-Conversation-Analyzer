from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AudioTranscriptionStartedResponse(BaseModel):
    transcription_id: UUID
    message_id: UUID
    status: str
    message: str
    reused: bool = False


class AudioTranscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    message_id: UUID
    status: str
    transcribed_text: str | None = None
    transcription_provider: str
    transcription_model: str
    duration_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.conversation.types import MessageType, ParticipantRole


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationRead]
    total: int


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    role: ParticipantRole


class SetOwnerRequest(BaseModel):
    participant_id: UUID


class ManualTranscriptionCreate(BaseModel):
    """Anexa texto de transcrição a uma mensagem já importada do WhatsApp."""

    text: str = Field(min_length=1, max_length=20_000)
    message_id: UUID


class MessageRead(BaseModel):
    id: UUID
    sender_id: UUID | None
    sender_name: str | None
    timestamp: datetime
    type: MessageType
    content: str
    metadata: dict[str, Any]


class ConversationDetail(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    participants: list[ParticipantRead]
    messages: list[MessageRead]
    total_messages: int
    offset: int
    limit: int


class ImportSummary(BaseModel):
    conversation_id: UUID
    total_messages: int
    skipped_lines: int
    participants: list[ParticipantRead]
    first_message_at: datetime | None
    last_message_at: datetime | None
    import_format: str = "txt"
    messages_added: int = 0
    messages_skipped_duplicate: int = 0
    audio_files_found: int = 0
    audio_files_matched: int = 0
    audio_transcriptions_started: int = 0
    audio_transcriptions_reused: int = 0

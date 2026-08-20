from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SuggestionsRequest(BaseModel):
    """Mensagem recebida agora (copiada do WhatsApp) para sugerir resposta."""

    incoming_message: str = Field(min_length=1, max_length=4000)


class SuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    suggested_text: str
    created_at: datetime


class SuggestionsResponse(BaseModel):
    conversation_id: UUID
    based_on_message_id: UUID | None = None
    incoming_message: str
    suggestions: list[SuggestionRead] = Field(min_length=4, max_length=4)
    llm_provider: str
    llm_model: str

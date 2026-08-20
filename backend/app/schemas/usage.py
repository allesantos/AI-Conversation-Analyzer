from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID | None
    operation: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    audio_seconds: float | None
    estimated_cost: float
    created_at: datetime


class UsageSummary(BaseModel):
    total_records: int
    total_input_tokens: int
    total_output_tokens: int
    total_audio_seconds: float
    total_estimated_cost: float
    records: list[UsageRecord]

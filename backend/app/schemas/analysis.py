from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SignalRead(BaseModel):
    key: str
    label: str
    participant: str
    strength: float
    observation: str
    message_ids: list[UUID]
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    signal_key: str
    signal_label: str
    polarity: str
    message_ids: list[UUID]
    observation: str


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    summary: str
    metrics: dict[str, Any]
    llm_provider: str
    llm_model: str
    input_tokens: int
    output_tokens: int
    interest_score: int | None = None
    interest_level: str | None = None
    confidence_score: int | None = None
    positive_signals: list[dict[str, Any]] = Field(default_factory=list)
    neutral_signals: list[dict[str, Any]] = Field(default_factory=list)
    negative_signals: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AnalyzeResponse(BaseModel):
    analysis: AnalysisRead
    observations: list[str]
    inferences: list[str]
    context_strategy: str
    interest_score: int | None = None
    interest_level: str | None = None
    confidence_score: int | None = None
    positive_signals: list[SignalRead] = Field(default_factory=list)
    neutral_signals: list[SignalRead] = Field(default_factory=list)
    negative_signals: list[SignalRead] = Field(default_factory=list)
    evidence: list[EvidenceRead] = Field(default_factory=list)
    reciprocity: dict[str, Any] | None = None
    summary_stale: bool = False
    from_cache: bool = False


class ProcessingStatusResponse(BaseModel):
    status: str
    message: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AskResponse(BaseModel):
    answer: str
    observations: list[str]
    inferences: list[str]
    llm_provider: str
    llm_model: str
    context_strategy: str


class TimelinePeriodRead(BaseModel):
    key: str
    label: str
    message_count: int
    interest_score: int
    interest_level: str
    confidence_score: int
    positive_count: int
    neutral_count: int
    negative_count: int
    summary_observation: str


class TimelineRead(BaseModel):
    conversation_id: UUID
    periods: list[TimelinePeriodRead]

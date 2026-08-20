from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.interest_engine.types import InterestLevel
from app.schemas.usage import UsageSummary


class DashboardConversationItem(BaseModel):
    id: UUID
    title: str
    updated_at: datetime
    total_messages: int
    interest_level: str | None = None
    interest_score: int | None = None
    confidence_score: int | None = None
    analyzed_at: datetime | None = None


class DashboardSummary(BaseModel):
    total_conversations: int
    analyzed_conversations: int
    interest_distribution: dict[str, int] = Field(
        default_factory=lambda: {level.value: 0 for level in InterestLevel}
    )
    recent: list[DashboardConversationItem]
    usage: UsageSummary

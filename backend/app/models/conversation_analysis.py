from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation

JSONType = JSON().with_variant(JSONB(), "postgresql")


class ConversationAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Análise da conversa: resumo (Fase 3) + interesse/reciprocidade (Fase 5)."""

    __tablename__ = "conversation_analyses"
    __table_args__ = (
        UniqueConstraint("conversation_id", name="uq_conversation_analyses_conversation_id"),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interest_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interest_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    positive_signals: Mapped[list[dict[str, object]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    neutral_signals: Mapped[list[dict[str, object]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    negative_signals: Mapped[list[dict[str, object]]] = mapped_column(
        JSONType, nullable=False, default=list
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="analysis")
    evidence: Mapped[list["AnalysisEvidence"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class AnalysisEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analysis_evidence"

    conversation_analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_key: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_label: Mapped[str] = mapped_column(String(200), nullable=False)
    polarity: Mapped[str] = mapped_column(String(16), nullable=False)
    message_ids: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    observation: Mapped[str] = mapped_column(Text, nullable=False)

    analysis: Mapped["ConversationAnalysis"] = relationship(back_populates="evidence")

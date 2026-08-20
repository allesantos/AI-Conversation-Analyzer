"""Registro básico de consumo de embeddings (AIUsage completo vem na Fase 8)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class EmbeddingUsageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "embedding_usage_records"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    chunks_embedded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_embedded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    embedding_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    conversation: Mapped[Conversation] = relationship(back_populates="embedding_usage")

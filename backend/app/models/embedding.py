from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation

JSONType = JSON().with_variant(JSONB(), "postgresql")
VectorType = Vector(1536).with_variant(JSON, "sqlite")


class MessageEmbedding(UUIDPrimaryKeyMixin, Base):
    """Chunk embedado de uma conversa (agrupamento de até N mensagens)."""

    __tablename__ = "message_embeddings"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_ids: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VectorType, nullable=False)
    chunk_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONType,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="embeddings")


class ConversationEmbeddingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_embedding_jobs"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    chunks_embedded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_embedded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="embedding_job")

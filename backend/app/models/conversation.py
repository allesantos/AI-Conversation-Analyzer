from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation_analysis import ConversationAnalysis
    from app.models.embedding import ConversationEmbeddingJob, MessageEmbedding
    from app.models.embedding_usage import EmbeddingUsageRecord
    from app.models.message import Message
    from app.models.participant import Participant
    from app.models.user import User


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    user: Mapped["User"] = relationship(back_populates="conversations")
    participants: Mapped[list["Participant"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    analysis: Mapped["ConversationAnalysis | None"] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )
    embeddings: Mapped[list["MessageEmbedding"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    embedding_job: Mapped["ConversationEmbeddingJob | None"] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )
    embedding_usage: Mapped["EmbeddingUsageRecord | None"] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )

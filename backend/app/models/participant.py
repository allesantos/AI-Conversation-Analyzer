from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message


class Participant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("conversation_id", "name", name="uq_participants_conversation_id_name"),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="participants")
    messages: Mapped[list["Message"]] = relationship(back_populates="sender")

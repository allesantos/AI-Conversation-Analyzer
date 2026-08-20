from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.conversation.types import MessageType


@dataclass(slots=True, frozen=True)
class MetricMessage:
    id: UUID
    sender_id: UUID | None
    sender_name: str | None
    timestamp: datetime
    message_type: MessageType
    content: str

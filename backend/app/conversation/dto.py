from dataclasses import dataclass, field
from datetime import datetime

from app.conversation.types import MessageType, ParticipantRole


@dataclass(slots=True, frozen=True)
class ParsedMessage:
    timestamp: datetime
    sender_name: str | None
    content: str
    message_type: MessageType
    metadata: dict[str, object] = field(default_factory=dict)
    line_number: int = 0


@dataclass(slots=True, frozen=True)
class NormalizedParticipant:
    name: str
    role: ParticipantRole


@dataclass(slots=True, frozen=True)
class NormalizedMessage:
    sender_name: str | None
    timestamp: datetime
    message_type: MessageType
    content: str
    metadata: dict[str, object]

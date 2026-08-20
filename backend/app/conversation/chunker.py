"""Agrupa mensagens em chunks para embedding (janela de N mensagens)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.conversation.metric_message import MetricMessage
from app.conversation.types import MessageType

_DEFAULT_CHUNK_SIZE = 8


@dataclass(slots=True, frozen=True)
class MessageChunk:
    conversation_id: UUID
    message_ids: list[UUID]
    chunk_text: str
    start_timestamp: datetime
    end_timestamp: datetime
    metadata: dict[str, object] = field(default_factory=dict)


def chunk_messages(
    conversation_id: UUID,
    messages: list[MetricMessage],
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> list[MessageChunk]:
    """Agrupa mensagens consecutivas preservando remetente e timestamp por linha."""
    ordered = sorted(messages, key=lambda item: (item.timestamp, str(item.id)))
    analyzable = [item for item in ordered if item.message_type != MessageType.SYSTEM]
    if not analyzable:
        return []

    chunks: list[MessageChunk] = []
    for start in range(0, len(analyzable), chunk_size):
        window = analyzable[start : start + chunk_size]
        lines: list[str] = []
        for item in window:
            sender = item.sender_name or "Desconhecido"
            lines.append(f"[{item.timestamp.isoformat()}] {sender}: {item.content.strip()}")
        participants = sorted({item.sender_name for item in window if item.sender_name})
        chunks.append(
            MessageChunk(
                conversation_id=conversation_id,
                message_ids=[item.id for item in window],
                chunk_text="\n".join(lines),
                start_timestamp=window[0].timestamp,
                end_timestamp=window[-1].timestamp,
                metadata={"message_count": len(window), "participants": participants},
            )
        )
    return chunks

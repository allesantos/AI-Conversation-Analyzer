from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.conversation.metric_message import MetricMessage
from app.conversation.types import MessageType


def synthetic_messages(
    count: int,
    *,
    sender: str = "Ana",
    prefix: str = "Mensagem",
) -> list[MetricMessage]:
    base = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    messages: list[MetricMessage] = []
    for index in range(count):
        content = f"{prefix} {index}"
        if index % 17 == 0:
            content += "?"
        messages.append(
            MetricMessage(
                id=uuid4(),
                sender_id=uuid4(),
                sender_name=sender if index % 5 else "Bruno",
                timestamp=base + timedelta(minutes=index),
                message_type=MessageType.TEXT,
                content=content,
            )
        )
    return messages

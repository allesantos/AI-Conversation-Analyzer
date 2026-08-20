from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.conversation.metric_message import MetricMessage
from app.conversation.metrics import calculate_conversation_metrics
from app.conversation.types import MessageType


def _msg(
    *,
    sender: str | None,
    content: str,
    at: datetime,
    message_type: MessageType = MessageType.TEXT,
) -> MetricMessage:
    return MetricMessage(
        id=uuid4(),
        sender_id=uuid4() if sender else None,
        sender_name=sender,
        timestamp=at,
        message_type=message_type,
        content=content,
    )


def test_empty_conversation_metrics() -> None:
    metrics = calculate_conversation_metrics([])
    assert metrics["total_messages"] == 0
    assert metrics["messages_by_participant"] == {}


def test_message_counts_and_proportions() -> None:
    base = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    messages = [
        _msg(sender="Ana", content="Oi", at=base),
        _msg(sender="Ana", content="Tudo bem?", at=base + timedelta(minutes=1)),
        _msg(sender="Bruno", content="Sim", at=base + timedelta(minutes=2)),
    ]
    metrics = calculate_conversation_metrics(messages, gap_hours=4)
    assert metrics["total_analyzable_messages"] == 3
    assert metrics["messages_by_participant"] == {"Ana": 2, "Bruno": 1}
    assert metrics["message_proportion_by_participant"]["Ana"] == pytest.approx(0.6667, rel=1e-3)
    assert metrics["questions_by_participant"]["Ana"] == 1


def test_conversation_initiations_use_gap() -> None:
    base = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    messages = [
        _msg(sender="Ana", content="Início 1", at=base),
        _msg(sender="Bruno", content="Resposta", at=base + timedelta(hours=1)),
        _msg(sender="Ana", content="Início 2", at=base + timedelta(hours=5, minutes=1)),
    ]
    metrics = calculate_conversation_metrics(messages, gap_hours=4)
    assert metrics["conversation_initiations"] == {"Ana": 2}


def test_response_time_stats() -> None:
    base = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    messages = [
        _msg(sender="Ana", content="Oi", at=base),
        _msg(sender="Bruno", content="Oi", at=base + timedelta(minutes=10)),
        _msg(sender="Ana", content="Voltou", at=base + timedelta(minutes=25)),
    ]
    metrics = calculate_conversation_metrics(messages)
    stats = metrics["response_time_seconds"]
    assert stats["count"] == 2
    assert stats["min"] == 600.0
    assert stats["max"] == 900.0
    assert stats["median"] == 750.0


def test_one_sided_conversation_has_no_response_times() -> None:
    base = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    messages = [
        _msg(sender="Ana", content="Oi?", at=base),
        _msg(sender="Ana", content="Cadê você?", at=base + timedelta(hours=1)),
    ]
    metrics = calculate_conversation_metrics(messages)
    assert metrics["response_time_seconds"]["count"] == 0
    assert metrics["conversation_initiations"]["Ana"] == 1


def test_media_counts_and_frequency() -> None:
    base = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    messages = [
        _msg(sender="Ana", content="foto", at=base, message_type=MessageType.IMAGE),
        _msg(
            sender="Bruno",
            content="audio",
            at=base + timedelta(days=1),
            message_type=MessageType.AUDIO,
        ),
        _msg(sender=None, content="Sistema", at=base, message_type=MessageType.SYSTEM),
    ]
    metrics = calculate_conversation_metrics(messages)
    assert metrics["total_messages"] == 3
    assert metrics["total_system_messages"] == 1
    assert metrics["media_counts"]["image"] == 1
    assert metrics["media_counts"]["audio"] == 1
    assert len(metrics["frequency"]["messages_per_day"]) == 2

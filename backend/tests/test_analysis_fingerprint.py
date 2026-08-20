from datetime import UTC, datetime
from uuid import uuid4

from app.conversation.analysis_fingerprint import compute_analysis_fingerprint
from app.conversation.metric_message import MetricMessage
from app.conversation.types import MessageType


def test_fingerprint_is_stable_for_same_messages() -> None:
    message_id = uuid4()
    sender_id = uuid4()
    timestamp = datetime(2026, 8, 18, 14, 30, tzinfo=UTC)
    messages = [
        MetricMessage(
            id=message_id,
            sender_id=sender_id,
            sender_name="Giulia",
            timestamp=timestamp,
            message_type=MessageType.TEXT,
            content="Oi!",
        )
    ]

    first = compute_analysis_fingerprint(messages)
    second = compute_analysis_fingerprint(list(messages))

    assert first == second


def test_fingerprint_ignores_message_and_participant_ids() -> None:
    timestamp = datetime(2026, 8, 18, 14, 30, tzinfo=UTC)
    original = MetricMessage(
        id=uuid4(),
        sender_id=uuid4(),
        sender_name="Giulia",
        timestamp=timestamp,
        message_type=MessageType.TEXT,
        content="Oi!",
    )
    reimported = MetricMessage(
        id=uuid4(),
        sender_id=uuid4(),
        sender_name="Giulia",
        timestamp=timestamp,
        message_type=MessageType.TEXT,
        content="Oi!",
    )

    assert compute_analysis_fingerprint([original]) == compute_analysis_fingerprint([reimported])


def test_fingerprint_changes_when_content_changes() -> None:
    base = MetricMessage(
        id=uuid4(),
        sender_id=uuid4(),
        sender_name="Giulia",
        timestamp=datetime(2026, 8, 18, 14, 30, tzinfo=UTC),
        message_type=MessageType.AUDIO,
        content="Áudio antigo",
    )
    updated = MetricMessage(
        id=base.id,
        sender_id=base.sender_id,
        sender_name=base.sender_name,
        timestamp=base.timestamp,
        message_type=base.message_type,
        content="Transcrição nova",
    )

    assert compute_analysis_fingerprint([base]) != compute_analysis_fingerprint([updated])

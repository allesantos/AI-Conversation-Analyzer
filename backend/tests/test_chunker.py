from uuid import uuid4

from app.conversation.chunker import chunk_messages
from tests.helpers.synthetic import synthetic_messages


def test_chunk_messages_groups_and_preserves_metadata() -> None:
    conversation_id = uuid4()
    messages = synthetic_messages(10)
    chunks = chunk_messages(conversation_id, messages, chunk_size=4)
    assert len(chunks) == 3
    assert chunks[0].metadata["message_count"] == 4
    assert "Ana:" in chunks[0].chunk_text or "Bruno:" in chunks[0].chunk_text
    assert "[" in chunks[0].chunk_text
    assert len(chunks[0].message_ids) == 4

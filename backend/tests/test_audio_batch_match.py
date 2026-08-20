from datetime import UTC, datetime
from uuid import UUID

from app.conversation.audio_batch_match import (
    AudioMatchCandidate,
    ZipAudioInput,
    match_audio_files_to_messages,
)


def test_match_audio_by_whatsapp_filename_index() -> None:
    day_ms = int(datetime(2026, 8, 18, 11, 0, tzinfo=UTC).timestamp() * 1000)
    hidden_one = UUID("00000000-0000-4000-8000-000000000001")
    hidden_two = UUID("00000000-0000-4000-8000-000000000002")
    candidates = [
        AudioMatchCandidate(message_id=hidden_one, timestamp_ms=day_ms + 60_000),
        AudioMatchCandidate(message_id=hidden_two, timestamp_ms=day_ms + 180_000),
    ]
    files = [
        ZipAudioInput(
            file_key="a0",
            filename="PTT-20260818-WA0000.opus",
            modified_ms=day_ms + 60_000,
        ),
        ZipAudioInput(
            file_key="a1",
            filename="PTT-20260818-WA0001.opus",
            modified_ms=day_ms + 180_000,
        ),
    ]

    matches = match_audio_files_to_messages(files, candidates)

    assert matches["a0"].message_id == hidden_one
    assert matches["a1"].message_id == hidden_two

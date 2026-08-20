from app.ai.transcription.whisper_compat import whisper_upload_filename


def test_opus_is_sent_as_ogg_to_whisper() -> None:
    assert (
        whisper_upload_filename(
            file_path="/storage/audio/conv/uuid.opus",
            original_filename="PTT-20260818-WA0000.opus",
        )
        == "PTT-20260818-WA0000.ogg"
    )


def test_ogg_is_unchanged() -> None:
    assert (
        whisper_upload_filename(
            file_path="/storage/audio/conv/uuid.ogg",
            original_filename="voice.ogg",
        )
        == "voice.ogg"
    )

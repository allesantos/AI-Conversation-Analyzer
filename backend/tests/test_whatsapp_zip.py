import io
import zipfile
from datetime import datetime

import pytest

from app.conversation.whatsapp_zip import extract_whatsapp_archive
from app.core.exceptions import BadRequestError


def test_extract_whatsapp_archive_finds_chat_and_audio() -> None:
    chat = (
        "18/08/2026 11:00 - Giulia: oi\n"
        "18/08/2026 11:01 - Giulia: <Mídia oculta>\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("_chat.txt", chat)
        info = zipfile.ZipInfo("PTT-20260818-WA0000.opus")
        info.date_time = (2026, 8, 18, 11, 1, 0)
        archive.writestr(info, b"fake-opus")
    payload = buffer.getvalue()

    extracted = extract_whatsapp_archive(
        payload,
        max_uncompressed_bytes=1024 * 1024,
        max_files=20,
    )

    assert extracted.chat_filename == "_chat.txt"
    assert "Giulia" in extracted.chat_text
    assert len(extracted.audio_files) == 1
    assert extracted.audio_files[0].filename == "PTT-20260818-WA0000.opus"


def test_extract_whatsapp_archive_rejects_missing_txt() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.md", "no chat here")
    payload = buffer.getvalue()

    with pytest.raises(BadRequestError, match="txt"):
        extract_whatsapp_archive(
            payload,
            max_uncompressed_bytes=1024 * 1024,
            max_files=20,
        )

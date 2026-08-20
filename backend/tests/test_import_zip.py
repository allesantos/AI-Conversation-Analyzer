import io
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from tests.test_audio import client_with_audio  # noqa: F401

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp"

ZIP_CHAT = """18/08/2026 11:00 - Giulia: oi
18/08/2026 11:01 - Giulia: <Mídia oculta>
18/08/2026 11:02 - Alle: tudo bem?
18/08/2026 11:03 - Giulia: <Mídia oculta>
"""


def _build_zip_with_hidden_audios() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("_chat.txt", ZIP_CHAT)
        for sequence, minute in ((0, 1), (1, 3)):
            filename = f"PTT-20260818-WA{sequence:04d}.opus"
            info = zipfile.ZipInfo(filename)
            info.date_time = (2026, 8, 18, 11, minute, 0)
            archive.writestr(info, b"fake-opus-content")
    return buffer.getvalue()


def _zip_upload() -> tuple[str, bytes, str]:
    return ("chat.zip", _build_zip_with_hidden_audios(), "application/zip")


async def _create_conversation(client: AsyncClient, headers: dict[str, str], title: str) -> str:
    created = await client.post("/api/v1/conversations", headers=headers, json={"title": title})
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def test_import_zip_starts_transcriptions_for_hidden_media(client_with_audio) -> None:
    client, _fake_llm = client_with_audio
    headers = await auth_headers(client, "zip@example.com")
    conversation_id = await _create_conversation(client, headers, "Zip import")

    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _zip_upload()},
        data={"owner_name": "Alle"},
    )
    assert imported.status_code == 200, imported.text
    summary = imported.json()
    assert summary["import_format"] == "zip"
    assert summary["total_messages"] == 4
    assert summary["audio_files_found"] == 2
    assert summary["audio_files_matched"] == 2
    assert summary["audio_transcriptions_started"] == 2

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    audio_messages = [item for item in detail.json()["messages"] if item["type"] == "AUDIO"]
    assert len(audio_messages) == 2
    assert all(item["metadata"].get("transcribed") for item in audio_messages)

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.llm.fake_provider import FakeLLMProvider
from app.ai.rag.in_memory_vector_store import InMemoryVectorStore
from app.ai.transcription.fake_provider import FakeTranscriptionProvider
from app.ai.transcription.provider import TranscriptionResult
from app.api.deps import (
    get_embedding_provider,
    get_embedding_service,
    get_llm_provider,
    get_transcription_provider,
    get_transcription_service,
    get_vector_store,
)
from app.services.analysis import AnalysisService
from app.core.config import Settings
from app.core.db import get_db
from app.services.audio_storage import AudioStorageService
from app.services.embedding import EmbeddingGenerationService
from app.services.embedding_enqueue import InlineEmbeddingJobEnqueuer
from app.services.transcription import TranscriptionService
from app.services.transcription_enqueue import InlineTranscriptionJobEnqueuer
from tests.conftest import auth_headers

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp"


def _audio_bytes() -> bytes:
    return b"fake-opus-content-for-tests"


def _txt(name: str) -> tuple[str, bytes, str]:
    path = FIXTURES / name
    return (name, path.read_bytes(), "text/plain")


@pytest.fixture
async def client_with_audio(
    app, tmp_path: Path
) -> AsyncGenerator[tuple[AsyncClient, FakeLLMProvider], None]:
    fake_llm = FakeLLMProvider(
        summary_text="Resumo fictício com áudio transcrito.",
        ask_text="Resposta fictícia mencionando o áudio transcrito.",
    )
    fake_embeddings = FakeEmbeddingProvider()
    fake_transcription = FakeTranscriptionProvider()
    in_memory_store = InMemoryVectorStore()
    settings = Settings(
        transcription_provider="fake",
        audio_storage_path=str(tmp_path / "audio"),
        max_upload_bytes=1024,
    )

    def override_embedding_service(
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> EmbeddingGenerationService:
        service = EmbeddingGenerationService(
            session,
            settings,
            fake_embeddings,
            in_memory_store,
            InlineEmbeddingJobEnqueuer(lambda _cid: None),
        )

        async def inline_generate(conversation_id):
            await service.generate_for_conversation(conversation_id)

        service.job_enqueuer = InlineEmbeddingJobEnqueuer(inline_generate)
        return service

    def override_transcription_service(
        session: Annotated[AsyncSession, Depends(get_db)],
        embedding_service: Annotated[EmbeddingGenerationService, Depends(get_embedding_service)],
    ) -> TranscriptionService:
        analysis_service = AnalysisService(session, settings, fake_llm, embedding_service)
        service = TranscriptionService(
            session,
            settings,
            fake_transcription,
            AudioStorageService(settings),
            InlineTranscriptionJobEnqueuer(lambda _tid: None),
            embedding_service,
            analysis_service,
        )

        async def inline_transcribe(transcription_id):
            await service.process_transcription(transcription_id)

        service.job_enqueuer = InlineTranscriptionJobEnqueuer(inline_transcribe)
        return service

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    app.dependency_overrides[get_vector_store] = lambda _session: in_memory_store
    app.dependency_overrides[get_embedding_service] = override_embedding_service
    app.dependency_overrides[get_transcription_provider] = lambda: fake_transcription
    app.dependency_overrides[get_transcription_service] = override_transcription_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client, fake_llm

    for key in (
        get_llm_provider,
        get_embedding_provider,
        get_vector_store,
        get_embedding_service,
        get_transcription_provider,
        get_transcription_service,
    ):
        app.dependency_overrides.pop(key, None)


async def _create_and_import_audio(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Com áudio"},
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    txt = (
        b"18/08/2026 14:30 - Maria: PTT-20260818-WA0001.opus (arquivo anexado)\n"
        b"18/08/2026 14:31 - Alex: Oi!\n"
    )
    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": ("audio_chat.txt", txt, "text/plain")},
        data={"owner_name": "Alex"},
    )
    assert imported.status_code == 200, imported.text
    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    audio_message = next(item for item in detail.json()["messages"] if item["type"] == "AUDIO")
    return conversation_id, audio_message["id"]


async def _upload_audio(
    client: AsyncClient,
    headers: dict[str, str],
    conversation_id: str,
    message_id: str,
    *,
    filename: str = "clip.opus",
    content: bytes | None = None,
) -> dict:
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": (filename, content or _audio_bytes(), "audio/opus")},
        data={"message_id": message_id},
    )
    assert response.status_code == 202, response.text
    return response.json()


async def _create_and_import_hidden_media(
    client: AsyncClient, headers: dict[str, str]
) -> tuple[str, str]:
    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Com mídia oculta"},
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    txt = b"18/08/2026 14:30 - Maria: <M\xc3\xaddia oculta>\n18/08/2026 14:31 - Alex: Oi!\n"
    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": ("hidden_media_chat.txt", txt, "text/plain")},
        data={"owner_name": "Alex"},
    )
    assert imported.status_code == 200, imported.text
    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    hidden_message = next(
        item for item in detail.json()["messages"] if item["type"] == "MEDIA_OCULTA"
    )
    return conversation_id, hidden_message["id"]


async def test_transcription_updates_media_oculta_to_audio(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-hidden@example.com")
    conversation_id, message_id = await _create_and_import_hidden_media(client, headers)

    detail_before = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    hidden_before = next(m for m in detail_before.json()["messages"] if m["id"] == message_id)
    assert hidden_before["type"] == "MEDIA_OCULTA"

    started = await _upload_audio(client, headers, conversation_id, message_id)
    assert started["status"] == "PENDING"

    transcription = await client.get(
        f"/api/v1/conversations/{conversation_id}/audio/{started['transcription_id']}",
        headers=headers,
    )
    assert transcription.status_code == 200, transcription.text
    assert transcription.json()["status"] == "COMPLETED"

    detail_after = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    updated = next(m for m in detail_after.json()["messages"] if m["id"] == message_id)
    assert updated["type"] == "AUDIO"
    assert updated["metadata"]["transcribed"] is True
    assert updated["content"] == transcription.json()["transcribed_text"]


async def test_upload_rejects_invalid_extension(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-invalid@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, headers)

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": ("not-audio.txt", b"hello", "text/plain")},
        data={"message_id": message_id},
    )
    assert response.status_code == 400


async def test_upload_rejects_oversized_file(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-big@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, headers)

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": ("big.opus", b"x" * 2048, "audio/opus")},
        data={"message_id": message_id},
    )
    assert response.status_code == 413


async def test_upload_transcription_updates_message(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-flow@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, headers)

    started = await _upload_audio(client, headers, conversation_id, message_id)
    assert started["status"] == "PENDING"

    transcription = await client.get(
        f"/api/v1/conversations/{conversation_id}/audio/{started['transcription_id']}",
        headers=headers,
    )
    assert transcription.status_code == 200, transcription.text
    body = transcription.json()
    assert body["status"] == "COMPLETED"
    assert body["transcribed_text"]
    assert "Transcrição fictícia" in body["transcribed_text"]

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    audio_message = next(item for item in detail.json()["messages"] if item["id"] == message_id)
    assert audio_message["content"] == body["transcribed_text"]
    assert audio_message["metadata"]["transcribed"] is True


async def test_transcription_refreshes_existing_analysis_without_deleting_it(
    client_with_audio,
) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-invalidate@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, headers)

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze", headers=headers
    )
    assert analyzed.status_code == 200, analyzed.text

    await _upload_audio(client, headers, conversation_id, message_id)

    refreshed = await client.get(
        f"/api/v1/conversations/{conversation_id}/analysis", headers=headers
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["summary_stale"] is True


async def test_audio_endpoint_isolates_users(client_with_audio) -> None:
    client, _ = client_with_audio
    owner_headers = await auth_headers(client, "audio-owner@example.com")
    other_headers = await auth_headers(client, "audio-other@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, owner_headers)
    started = await _upload_audio(client, owner_headers, conversation_id, message_id)

    forbidden = await client.get(
        f"/api/v1/conversations/{conversation_id}/audio/{started['transcription_id']}",
        headers=other_headers,
    )
    assert forbidden.status_code == 404


async def test_transcribed_text_used_by_analyze_and_ask(client_with_audio) -> None:
    client, fake_llm = client_with_audio
    headers = await auth_headers(client, "audio-integrate@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, headers)
    started = await _upload_audio(client, headers, conversation_id, message_id)

    transcription = await client.get(
        f"/api/v1/conversations/{conversation_id}/audio/{started['transcription_id']}",
        headers=headers,
    )
    transcribed_text = transcription.json()["transcribed_text"]

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze", headers=headers
    )
    assert analyzed.status_code == 200, analyzed.text
    assert any(transcribed_text in str(call["user_prompt"]) for call in fake_llm.calls)

    asked = await client.post(
        f"/api/v1/conversations/{conversation_id}/ask",
        headers=headers,
        json={"question": "O que foi dito no áudio?"},
    )
    assert asked.status_code == 200, asked.text
    assert any(transcribed_text in str(call["user_prompt"]) for call in fake_llm.calls)


async def test_metrics_reflect_transcribed_content(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-metrics@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, headers)

    before = await client.post(f"/api/v1/conversations/{conversation_id}/analyze", headers=headers)
    assert before.status_code == 200, before.text
    before_metrics = before.json()["analysis"]["metrics"]

    await _upload_audio(client, headers, conversation_id, message_id)

    after = await client.post(f"/api/v1/conversations/{conversation_id}/analyze", headers=headers)
    assert after.status_code == 200, after.text
    after_metrics = after.json()["analysis"]["metrics"]
    assert after_metrics != before_metrics


class FailingTranscriptionProvider:
    """Provider que sempre falha — para testar tratamento de erro."""

    async def transcribe_file(self, file_path: str, *, filename: str) -> TranscriptionResult:
        raise RuntimeError("Erro simulado de transcrição")


@pytest.fixture
async def client_with_failing_audio(
    app, tmp_path: Path
) -> AsyncGenerator[tuple[AsyncClient, None], None]:
    fake_embeddings = FakeEmbeddingProvider()
    fake_llm = FakeLLMProvider()
    failing_provider = FailingTranscriptionProvider()
    in_memory_store = InMemoryVectorStore()
    settings = Settings(
        transcription_provider="fake",
        audio_storage_path=str(tmp_path / "audio"),
        max_upload_bytes=1024,
    )

    def override_embedding_service(
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> EmbeddingGenerationService:
        service = EmbeddingGenerationService(
            session,
            settings,
            fake_embeddings,
            in_memory_store,
            InlineEmbeddingJobEnqueuer(lambda _cid: None),
        )

        async def inline_generate(conversation_id):
            await service.generate_for_conversation(conversation_id)

        service.job_enqueuer = InlineEmbeddingJobEnqueuer(inline_generate)
        return service

    def override_transcription_service(
        session: Annotated[AsyncSession, Depends(get_db)],
        embedding_service: Annotated[EmbeddingGenerationService, Depends(get_embedding_service)],
    ) -> TranscriptionService:
        service = TranscriptionService(
            session,
            settings,
            failing_provider,
            AudioStorageService(settings),
            InlineTranscriptionJobEnqueuer(lambda _tid: None),
            embedding_service,
        )

        async def inline_transcribe(transcription_id):
            try:
                await service.process_transcription(transcription_id)
            except RuntimeError:
                pass

        service.job_enqueuer = InlineTranscriptionJobEnqueuer(inline_transcribe)
        return service

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    app.dependency_overrides[get_vector_store] = lambda _session: in_memory_store
    app.dependency_overrides[get_embedding_service] = override_embedding_service
    app.dependency_overrides[get_transcription_provider] = lambda: failing_provider
    app.dependency_overrides[get_transcription_service] = override_transcription_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client, None

    for key in (
        get_llm_provider,
        get_embedding_provider,
        get_vector_store,
        get_embedding_service,
        get_transcription_provider,
        get_transcription_service,
    ):
        app.dependency_overrides.pop(key, None)


async def test_transcription_failure_marks_failed_and_preserves_message(
    client_with_failing_audio,
) -> None:
    client, _ = client_with_failing_audio
    headers = await auth_headers(client, "audio-fail@example.com")
    conversation_id, message_id = await _create_and_import_audio(client, headers)

    detail_before = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    audio_msg_before = next(m for m in detail_before.json()["messages"] if m["id"] == message_id)
    original_content = audio_msg_before["content"]

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": ("clip.opus", b"fake-opus-content-for-tests", "audio/opus")},
        data={"message_id": message_id},
    )
    assert response.status_code == 202, response.text
    started = response.json()
    transcription_id = started["transcription_id"]

    status_resp = await client.get(
        f"/api/v1/conversations/{conversation_id}/audio/{transcription_id}",
        headers=headers,
    )
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["status"] == "FAILED"
    assert body["error_message"]
    assert "Erro simulado" in body["error_message"]
    assert body["transcribed_text"] is None

    detail_after = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    audio_msg_after = next(m for m in detail_after.json()["messages"] if m["id"] == message_id)
    assert audio_msg_after["content"] == original_content


async def test_upload_with_sender_and_timestamp_marks_analysis_only(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-analysis-only@example.com")
    conversation_id, _ = await _create_and_import_hidden_media(client, headers)

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    maria = next(item for item in detail.json()["participants"] if item["name"] == "Maria")

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": ("PTT-20260818-WA0000.opus", _audio_bytes(), "audio/opus")},
        data={
            "sender_id": maria["id"],
            "timestamp": "2026-08-18T14:30:00-03:00",
        },
    )
    assert response.status_code == 202, response.text
    message_id = response.json()["message_id"]

    detail_after = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    created = next(item for item in detail_after.json()["messages"] if item["id"] == message_id)
    assert created["type"] == "AUDIO"
    assert created["metadata"]["analysis_only"] is True
    assert created["metadata"]["uploaded"] is True


async def test_get_message_returns_fresh_transcribed_content(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-get-message@example.com")
    conversation_id, _ = await _create_and_import_hidden_media(client, headers)

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    maria = next(item for item in detail.json()["participants"] if item["name"] == "Maria")

    started = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": ("PTT-20260818-WA0000.opus", _audio_bytes(), "audio/opus")},
        data={
            "sender_id": maria["id"],
            "timestamp": "2026-08-18T14:30:00-03:00",
        },
    )
    assert started.status_code == 202, started.text
    message_id = started.json()["message_id"]
    transcription_id = started.json()["transcription_id"]

    transcription = await client.get(
        f"/api/v1/conversations/{conversation_id}/audio/{transcription_id}",
        headers=headers,
    )
    assert transcription.status_code == 200, transcription.text
    transcribed_text = transcription.json()["transcribed_text"]

    message = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}",
        headers=headers,
    )
    assert message.status_code == 200, message.text
    body = message.json()
    assert body["content"] == transcribed_text
    assert body["metadata"]["analysis_only"] is True


async def test_delete_analysis_only_message_refreshes_analysis_without_llm(
    client_with_audio,
) -> None:
    client, fake_llm = client_with_audio
    headers = await auth_headers(client, "audio-delete-refresh@example.com")
    conversation_id, _ = await _create_and_import_hidden_media(client, headers)

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    maria = next(item for item in detail.json()["participants"] if item["name"] == "Maria")

    started = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": ("PTT-20260818-WA0000.opus", _audio_bytes(), "audio/opus")},
        data={
            "sender_id": maria["id"],
            "timestamp": "2026-08-18T14:30:00-03:00",
        },
    )
    assert started.status_code == 202, started.text
    message_id = started.json()["message_id"]

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert analyzed.status_code == 200, analyzed.text
    assert len(fake_llm.calls) == 1

    deleted = await client.delete(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text
    assert len(fake_llm.calls) == 1

    persisted = await client.get(
        f"/api/v1/conversations/{conversation_id}/analysis",
        headers=headers,
    )
    assert persisted.status_code == 200, persisted.text
    body = persisted.json()
    assert body["summary_stale"] is True
    assert body["analysis"]["summary"]

    cached = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert cached.status_code == 200, cached.text
    assert cached.json()["from_cache"] is False
    assert len(fake_llm.calls) == 2


async def test_delete_analysis_only_message_removes_it_and_invalidates_analysis(
    client_with_audio,
) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-delete@example.com")
    conversation_id, _ = await _create_and_import_hidden_media(client, headers)

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    maria = next(item for item in detail.json()["participants"] if item["name"] == "Maria")

    started = await client.post(
        f"/api/v1/conversations/{conversation_id}/audio",
        headers=headers,
        files={"file": ("PTT-20260818-WA0000.opus", _audio_bytes(), "audio/opus")},
        data={
            "sender_id": maria["id"],
            "timestamp": "2026-08-18T14:30:00-03:00",
        },
    )
    assert started.status_code == 202, started.text
    message_id = started.json()["message_id"]

    listed = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages/analysis-only",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == message_id for item in listed.json())

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert analyzed.status_code == 200, analyzed.text

    deleted = await client.delete(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    missing = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}",
        headers=headers,
    )
    assert missing.status_code == 404

    listed_after = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages/analysis-only",
        headers=headers,
    )
    assert listed_after.status_code == 200, listed_after.text
    assert all(item["id"] != message_id for item in listed_after.json())

    stale_analysis = await client.get(
        f"/api/v1/conversations/{conversation_id}/analysis",
        headers=headers,
    )
    assert stale_analysis.status_code == 200, stale_analysis.text
    assert stale_analysis.json()["summary_stale"] is True


async def test_delete_non_analysis_only_message_is_rejected(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "audio-delete-block@example.com")
    conversation_id, _ = await _create_and_import_hidden_media(client, headers)

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    message_id = detail.json()["messages"][0]["id"]

    response = await client.delete(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}",
        headers=headers,
    )
    assert response.status_code == 400, response.text


async def test_manual_transcription_attaches_to_hidden_media(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "manual-tx-attach@example.com")
    conversation_id, message_id = await _create_and_import_hidden_media(client, headers)

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/manual-transcription",
        headers=headers,
        json={
            "text": "Transcrição colada na mídia oculta.",
            "message_id": message_id,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == message_id
    assert body["type"] == "AUDIO"
    assert body["content"] == "Transcrição colada na mídia oculta."
    assert body["metadata"]["manual_transcription"] is True
    assert body["metadata"]["transcribed"] is True
    assert body["metadata"]["source_format"] == "plain"
    assert body["metadata"].get("analysis_only") is not True


async def test_manual_transcription_requires_message_id(client_with_audio) -> None:
    client, _ = client_with_audio
    headers = await auth_headers(client, "manual-tx-validation@example.com")
    conversation_id, _ = await _create_and_import_hidden_media(client, headers)

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/manual-transcription",
        headers=headers,
        json={"text": "Sem mensagem vinculada."},
    )
    assert response.status_code == 422, response.text

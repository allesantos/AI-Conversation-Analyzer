from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.llm.fake_provider import FakeLLMProvider
from app.ai.rag.in_memory_vector_store import InMemoryVectorStore
from app.ai.rag.types import ContextStrategy
from app.api.deps import (
    get_embedding_provider,
    get_embedding_service,
    get_llm_provider,
    get_vector_store,
)
from app.core.config import Settings
from app.core.db import get_db
from app.services.embedding import EmbeddingGenerationService
from app.services.embedding_enqueue import InlineEmbeddingJobEnqueuer
from tests.conftest import auth_headers

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp"


def _txt(name: str) -> tuple[str, bytes, str]:
    path = FIXTURES / name
    return (name, path.read_bytes(), "text/plain")


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider(
        summary_text="Resumo fictício gerado para testes.",
        ask_text="Resposta fictícia para a pergunta.",
    )


@pytest.fixture
async def client_with_ai(app, fake_llm: FakeLLMProvider):
    fake_embeddings = FakeEmbeddingProvider()
    in_memory_store = InMemoryVectorStore()

    def override_embedding_service(
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> EmbeddingGenerationService:
        settings = Settings()
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

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    app.dependency_overrides[get_vector_store] = lambda _session: in_memory_store
    app.dependency_overrides[get_embedding_service] = override_embedding_service

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client, fake_llm
    for key in (get_llm_provider, get_embedding_provider, get_vector_store, get_embedding_service):
        app.dependency_overrides.pop(key, None)


async def _create_and_import(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str,
    fixture: str = "standard_oneline.txt",
    owner_name: str = "Marina Costa",
) -> str:
    created = await client.post("/api/v1/conversations", headers=headers, json={"title": title})
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt(fixture)},
        data={"owner_name": owner_name},
    )
    assert imported.status_code == 200, imported.text
    return conversation_id


async def test_analyze_and_get_analysis(client_with_ai) -> None:
    client, fake_llm = client_with_ai
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_and_import(client, headers, title="Analisar")

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert analyzed.status_code == 200, analyzed.text
    body = analyzed.json()
    assert body["analysis"]["summary"] == "Resumo fictício gerado para testes."
    assert body["context_strategy"] == ContextStrategy.DIRECT.value
    assert body["observations"]
    assert body["inferences"]
    assert len(fake_llm.calls) == 1

    persisted = await client.get(
        f"/api/v1/conversations/{conversation_id}/analysis",
        headers=headers,
    )
    assert persisted.status_code == 200, persisted.text
    stored = persisted.json()
    assert stored["analysis"]["summary"] == body["analysis"]["summary"]
    assert stored["observations"] == body["observations"]
    assert stored["inferences"] == body["inferences"]
    assert stored["positive_signals"] == body["positive_signals"]
    assert stored["evidence"] == body["evidence"]


async def test_analyze_returns_cache_when_data_unchanged(client_with_ai) -> None:
    client, fake_llm = client_with_ai
    headers = await auth_headers(client, "cache@example.com")
    conversation_id = await _create_and_import(client, headers, title="Cache")

    first = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["from_cache"] is False
    assert len(fake_llm.calls) == 1

    second = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["from_cache"] is True
    assert len(fake_llm.calls) == 1

    forced = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
        params={"force": "true"},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["from_cache"] is False
    assert len(fake_llm.calls) == 2


async def test_reimport_same_txt_reuses_llm_cache(client_with_ai) -> None:
    client, fake_llm = client_with_ai
    headers = await auth_headers(client, "reimport@example.com")
    conversation_id = await _create_and_import(
        client,
        headers,
        title="Reimport",
        fixture="standard_oneline.txt",
    )

    first = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["from_cache"] is False
    assert len(fake_llm.calls) == 1

    reimported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("standard_oneline.txt")},
    )
    assert reimported.status_code == 200, reimported.text

    after_reimport = await client.get(
        f"/api/v1/conversations/{conversation_id}/analysis",
        headers=headers,
    )
    assert after_reimport.status_code == 200, after_reimport.text
    assert after_reimport.json()["summary_stale"] is False
    assert after_reimport.json()["analysis"]["summary"] == "Resumo fictício gerado para testes."

    second = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["from_cache"] is True
    assert len(fake_llm.calls) == 1


async def test_ask_uses_fake_llm(client_with_ai) -> None:
    client, fake_llm = client_with_ai
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_and_import(client, headers, title="Perguntar")

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/ask",
        headers=headers,
        json={"question": "Quem iniciou mais a conversa?"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["context_strategy"] == ContextStrategy.DIRECT.value
    assert len(fake_llm.calls) == 1


async def test_analyze_and_ask_do_not_leak_between_users(client_with_ai) -> None:
    client, _fake_llm = client_with_ai
    ana = await auth_headers(client, "ana@example.com")
    bruno = await auth_headers(client, "bruno@example.com")

    ana_id = await _create_and_import(client, ana, title="Privada Ana")

    analyze = await client.post(f"/api/v1/conversations/{ana_id}/analyze", headers=bruno)
    assert analyze.status_code == 404

    ask = await client.post(
        f"/api/v1/conversations/{ana_id}/ask",
        headers=bruno,
        json={"question": "Resumo?"},
    )
    assert ask.status_code == 404


async def test_get_analysis_without_running_returns_404(client_with_ai) -> None:
    client, _fake_llm = client_with_ai
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_and_import(client, headers, title="Sem análise")

    response = await client.get(
        f"/api/v1/conversations/{conversation_id}/analysis",
        headers=headers,
    )
    assert response.status_code == 404

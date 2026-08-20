from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.llm.fake_provider import FakeLLMProvider
from app.ai.rag.in_memory_vector_store import InMemoryVectorStore
from app.api.deps import (
    get_embedding_provider,
    get_embedding_service,
    get_llm_provider,
    get_vector_store,
)
from app.core.config import Settings
from app.core.db import get_db
from app.interest_engine.types import InterestLevel
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    for key in (get_llm_provider, get_embedding_provider, get_vector_store, get_embedding_service):
        app.dependency_overrides.pop(key, None)


async def test_dashboard_empty(client: AsyncClient) -> None:
    headers = await auth_headers(client, "dash-empty@example.com")
    response = await client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_conversations"] == 0
    assert body["analyzed_conversations"] == 0
    assert body["recent"] == []
    assert body["usage"]["total_records"] == 0
    assert set(body["interest_distribution"].keys()) == {level.value for level in InterestLevel}


async def test_dashboard_lists_conversations_and_analysis(client_with_ai: AsyncClient) -> None:
    client = client_with_ai
    headers = await auth_headers(client, "dash-full@example.com")

    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Dash Conv"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("standard_oneline.txt")},
        data={"owner_name": "Marina Costa"},
    )
    assert imported.status_code == 200, imported.text

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert analyzed.status_code == 200, analyzed.text
    analysis = analyzed.json()["analysis"]

    response = await client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_conversations"] == 1
    assert body["analyzed_conversations"] == 1
    assert len(body["recent"]) == 1
    item = body["recent"][0]
    assert item["id"] == conversation_id
    assert item["title"] == "Dash Conv"
    assert item["total_messages"] > 0
    assert item["interest_level"] == analysis["interest_level"]
    assert item["interest_score"] == analysis["interest_score"]
    assert body["interest_distribution"][analysis["interest_level"]] == 1
    assert body["usage"]["total_records"] >= 1


async def test_dashboard_isolates_users(client: AsyncClient) -> None:
    owner = await auth_headers(client, "dash-owner@example.com")
    other = await auth_headers(client, "dash-other@example.com")

    created = await client.post(
        "/api/v1/conversations",
        headers=owner,
        json={"title": "Privada"},
    )
    assert created.status_code == 201

    own = await client.get("/api/v1/dashboard", headers=owner)
    assert own.status_code == 200
    assert own.json()["total_conversations"] == 1

    foreign = await client.get("/api/v1/dashboard", headers=other)
    assert foreign.status_code == 200
    assert foreign.json()["total_conversations"] == 0
    assert foreign.json()["recent"] == []

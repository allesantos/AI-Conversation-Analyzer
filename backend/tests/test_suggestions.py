from __future__ import annotations

import re
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
from app.services.embedding import EmbeddingGenerationService
from app.services.embedding_enqueue import InlineEmbeddingJobEnqueuer
from tests.conftest import auth_headers

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp"

MANIPULATIVE_PATTERNS = [
    re.compile(r"você não vai responder", re.IGNORECASE),
    re.compile(r"se não responder", re.IGNORECASE),
    re.compile(r"última chance", re.IGNORECASE),
    re.compile(r"todo mundo", re.IGNORECASE),
    re.compile(r"fingir.*desinteresse", re.IGNORECASE),
    re.compile(r"ghosting", re.IGNORECASE),
    re.compile(r"faça.*ciúme", re.IGNORECASE),
    re.compile(r"manipul", re.IGNORECASE),
]

INCOMING = {"incoming_message": "Oi, tudo bem? Quer sair sábado?"}


def _txt(name: str) -> tuple[str, bytes, str]:
    path = FIXTURES / name
    return (name, path.read_bytes(), "text/plain")


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


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
        yield async_client, fake_llm
    for key in (
        get_llm_provider,
        get_embedding_provider,
        get_vector_store,
        get_embedding_service,
    ):
        app.dependency_overrides.pop(key, None)


async def _create_and_import(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str,
    fixture: str = "standard_oneline.txt",
) -> str:
    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": title},
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt(fixture)},
    )
    assert imported.status_code == 200, imported.text
    return conversation_id


async def test_suggestions_returns_4_categories(client_with_ai) -> None:
    client, _ = client_with_ai
    headers = await auth_headers(client, "sug@example.com")
    conversation_id = await _create_and_import(client, headers, title="Sugestões")

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/suggestions",
        headers=headers,
        json=INCOMING,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["suggestions"]) == 4
    categories = {s["category"] for s in body["suggestions"]}
    assert categories == {"NATURAL", "DIVERTIDA", "DIRETA", "CONSERVADORA"}
    assert body["based_on_message_id"] is None
    assert body["incoming_message"] == INCOMING["incoming_message"]
    assert body["llm_provider"] == "fake"


async def test_suggestions_requires_incoming_message(client_with_ai) -> None:
    client, _ = client_with_ai
    headers = await auth_headers(client, "sug-body@example.com")
    conversation_id = await _create_and_import(client, headers, title="Body")

    missing = await client.post(
        f"/api/v1/conversations/{conversation_id}/suggestions",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    blank = await client.post(
        f"/api/v1/conversations/{conversation_id}/suggestions",
        headers=headers,
        json={"incoming_message": "   "},
    )
    assert blank.status_code == 400
    assert "cole" in blank.json()["detail"].lower()


async def test_suggestions_no_manipulative_language(client_with_ai) -> None:
    client, _ = client_with_ai
    headers = await auth_headers(client, "sug-ethics@example.com")
    conversation_id = await _create_and_import(client, headers, title="Ética")

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/suggestions",
        headers=headers,
        json=INCOMING,
    )
    assert response.status_code == 200, response.text
    for suggestion in response.json()["suggestions"]:
        text = suggestion["suggested_text"]
        for pattern in MANIPULATIVE_PATTERNS:
            assert not pattern.search(text), (
                f"Sugestão '{text}' contém linguagem manipulativa: {pattern.pattern}"
            )


async def test_suggestions_isolates_users(client_with_ai) -> None:
    client, _ = client_with_ai
    owner_headers = await auth_headers(client, "sug-owner@example.com")
    other_headers = await auth_headers(client, "sug-other@example.com")
    conversation_id = await _create_and_import(client, owner_headers, title="Privada")

    forbidden = await client.post(
        f"/api/v1/conversations/{conversation_id}/suggestions",
        headers=other_headers,
        json=INCOMING,
    )
    assert forbidden.status_code == 404


async def test_suggestions_empty_conversation_returns_error(
    client_with_ai,
) -> None:
    client, _ = client_with_ai
    headers = await auth_headers(client, "sug-empty@example.com")
    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Vazia"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/suggestions",
        headers=headers,
        json=INCOMING,
    )
    assert response.status_code == 400
    assert "importe" in response.json()["detail"].lower()


async def test_suggestions_each_has_non_empty_text(client_with_ai) -> None:
    client, _ = client_with_ai
    headers = await auth_headers(client, "sug-text@example.com")
    conversation_id = await _create_and_import(client, headers, title="Texto")

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/suggestions",
        headers=headers,
        json=INCOMING,
    )
    assert response.status_code == 200, response.text
    for suggestion in response.json()["suggestions"]:
        assert suggestion["suggested_text"].strip()

from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.llm.fake_provider import FakeLLMProvider
from app.ai.rag.in_memory_vector_store import InMemoryVectorStore
from app.ai.rag.retriever import ConversationRetriever
from app.ai.rag.types import ContextStrategy
from app.ai.rag.vector_store import EmbeddingRecord
from app.api.deps import (
    get_embedding_provider,
    get_embedding_service,
    get_llm_provider,
    get_vector_store,
)
from app.conversation.context_builder import select_intermediate_messages
from app.core.config import Settings
from app.core.db import get_db
from app.services.embedding import EmbeddingGenerationService
from tests.conftest import auth_headers
from tests.helpers.rag import (
    build_embedding_service,
    create_conversation_with_messages,
    open_test_session,
)
from tests.helpers.synthetic import synthetic_messages


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def in_memory_store() -> InMemoryVectorStore:
    return InMemoryVectorStore()


@pytest.fixture
async def client_with_rag(app, fake_llm, fake_embeddings, in_memory_store):
    def override_embedding_service(
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> EmbeddingGenerationService:
        return build_embedding_service(session, Settings(), fake_embeddings, in_memory_store)

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    app.dependency_overrides[get_vector_store] = lambda _session: in_memory_store
    app.dependency_overrides[get_embedding_service] = override_embedding_service

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client, fake_llm, fake_embeddings, in_memory_store
    for key in (get_llm_provider, get_embedding_provider, get_vector_store, get_embedding_service):
        app.dependency_overrides.pop(key, None)


async def test_intermediate_strategy_analyzes_over_direct_limit(client_with_rag, app) -> None:
    client, fake_llm, _embeddings, _store = client_with_rag
    headers = await auth_headers(client, "ana@example.com")
    session = await open_test_session(app)
    conversation_id = await create_conversation_with_messages(
        client,
        headers,
        title="Intermediária",
        message_count=2500,
        session=session,
    )

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze", headers=headers
    )
    assert analyzed.status_code == 200, analyzed.text
    body = analyzed.json()
    assert body["context_strategy"] == ContextStrategy.SUMMARY_SELECTION.value
    assert len(fake_llm.calls) == 1


async def test_rag_strategy_returns_processing_until_embeddings_ready(client_with_rag, app) -> None:
    client, _fake_llm, _embeddings, _store = client_with_rag
    headers = await auth_headers(client, "bruno@example.com")
    session = await open_test_session(app)
    conversation_id = await create_conversation_with_messages(
        client,
        headers,
        title="Grande RAG",
        message_count=10001,
        session=session,
    )

    first = await client.post(f"/api/v1/conversations/{conversation_id}/analyze", headers=headers)
    assert first.status_code == 202
    assert first.json()["status"] == "PENDING"


async def test_rag_strategy_works_after_inline_embedding_generation(
    client_with_rag,
    app,
    fake_embeddings,
    in_memory_store,
) -> None:
    client, fake_llm, _embeddings, store = client_with_rag
    headers = await auth_headers(client, "carla@example.com")
    session = await open_test_session(app)
    conversation_id = await create_conversation_with_messages(
        client,
        headers,
        title="Grande pronta",
        message_count=10001,
        session=session,
    )

    service = build_embedding_service(session, Settings(), fake_embeddings, in_memory_store)
    await service.generate_for_conversation(UUID(conversation_id))

    analyzed = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze", headers=headers
    )
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["context_strategy"] == ContextStrategy.RAG.value
    assert await store.count_for_conversation(UUID(conversation_id)) > 0
    assert len(fake_llm.calls) >= 1


async def test_vector_search_is_scoped_by_conversation_id(
    fake_embeddings: FakeEmbeddingProvider,
    in_memory_store: InMemoryVectorStore,
) -> None:
    conv_a = uuid4()
    conv_b = uuid4()
    vector = (await fake_embeddings.embed_texts(["conversa A sobre viagens"])).vectors[0]
    await in_memory_store.store(
        [
            EmbeddingRecord(
                id=uuid4(),
                conversation_id=conv_a,
                message_ids=[],
                chunk_text="conversa A sobre viagens",
                vector=vector,
                metadata={},
            )
        ]
    )
    retriever = ConversationRetriever(
        vector_store=in_memory_store,
        embedding_provider=fake_embeddings,
        top_k=3,
    )
    results = await retriever.retrieve(conv_b, "viagens")
    assert results == []


async def test_reimport_clears_embeddings(
    client_with_rag, app, fake_embeddings, in_memory_store
) -> None:
    client, _fake_llm, _embeddings, store = client_with_rag
    headers = await auth_headers(client, "dana@example.com")
    session = await open_test_session(app)
    conversation_id = await create_conversation_with_messages(
        client,
        headers,
        title="Reimport",
        message_count=10001,
        session=session,
    )

    service = build_embedding_service(session, Settings(), fake_embeddings, in_memory_store)
    await service.generate_for_conversation(UUID(conversation_id))
    assert await store.count_for_conversation(UUID(conversation_id)) > 0

    fixture = Path(__file__).parent / "fixtures" / "whatsapp" / "standard_oneline.txt"
    reimported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": ("standard_oneline.txt", fixture.read_bytes(), "text/plain")},
    )
    assert reimported.status_code == 200
    assert await store.count_for_conversation(UUID(conversation_id)) == 0


def test_select_intermediate_messages_prefers_recent_and_questions() -> None:
    settings = Settings(rag_intermediate_recent_messages=3, rag_intermediate_max_messages=5)
    messages = synthetic_messages(20)
    selected = select_intermediate_messages(messages, settings)
    assert len(selected) <= 5
    assert any(item.content.endswith("?") for item in selected)

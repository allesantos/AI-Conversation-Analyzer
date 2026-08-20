import pytest
from httpx import AsyncClient

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
from app.interest_engine.types import InterestLevel
from tests.conftest import auth_headers
from tests.helpers.interest_import import import_messages_scenario
from tests.helpers.interest_scenarios import (
    high_reciprocity_conversation,
    low_volume_conversation,
    one_sided_conversation,
)
from tests.helpers.rag import build_embedding_service


@pytest.fixture
async def client_with_interest(app, fake_llm: FakeLLMProvider):
    fake_embeddings = FakeEmbeddingProvider()
    in_memory_store = InMemoryVectorStore()

    from typing import Annotated

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.db import get_db

    def override_embedding_service_dep(
        session: Annotated[AsyncSession, Depends(get_db)],
    ):
        return build_embedding_service(session, Settings(), fake_embeddings, in_memory_store)

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    app.dependency_overrides[get_vector_store] = lambda _session: in_memory_store
    app.dependency_overrides[get_embedding_service] = override_embedding_service_dep

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    for key in (get_llm_provider, get_embedding_provider, get_vector_store, get_embedding_service):
        app.dependency_overrides.pop(key, None)


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider(
        summary_text="Com base nas evidências, os sinais sugerem reciprocidade moderada.",
    )


async def test_analyze_includes_interest_fields(client_with_interest) -> None:
    client = client_with_interest
    headers = await auth_headers(client, "interest@example.com")
    messages, owner, _other = high_reciprocity_conversation()
    conversation_id = await import_messages_scenario(
        client, headers, title="Alta reciprocidade", messages=messages, owner_name=owner
    )

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["interest_level"] in {level.value for level in InterestLevel}
    assert body["interest_score"] is not None
    assert body["confidence_score"] is not None
    assert body["positive_signals"]
    assert body["evidence"]
    for item in body["evidence"]:
        assert item["message_ids"]


async def test_timeline_endpoint_returns_periods(client_with_interest) -> None:
    client = client_with_interest
    headers = await auth_headers(client, "timeline@example.com")
    messages, owner, _other = high_reciprocity_conversation()
    conversation_id = await import_messages_scenario(
        client, headers, title="Timeline", messages=messages, owner_name=owner
    )

    response = await client.get(
        f"/api/v1/conversations/{conversation_id}/timeline", headers=headers
    )
    assert response.status_code == 200, response.text
    periods = response.json()["periods"]
    assert periods
    assert any(item["key"] == "full" for item in periods)


async def test_timeline_isolated_between_users(client_with_interest) -> None:
    client = client_with_interest
    owner_headers = await auth_headers(client, "owner-timeline@example.com")
    intruder_headers = await auth_headers(client, "intruder-timeline@example.com")
    messages, owner, _other = one_sided_conversation()
    conversation_id = await import_messages_scenario(
        client, owner_headers, title="Privada", messages=messages, owner_name=owner
    )

    denied = await client.get(
        f"/api/v1/conversations/{conversation_id}/timeline",
        headers=intruder_headers,
    )
    assert denied.status_code == 404


async def test_low_volume_analyze_has_low_confidence(client_with_interest) -> None:
    client = client_with_interest
    headers = await auth_headers(client, "lowvol@example.com")
    messages, owner, _other = low_volume_conversation()
    conversation_id = await import_messages_scenario(
        client, headers, title="Baixo volume", messages=messages, owner_name=owner
    )

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["confidence_score"] <= 35

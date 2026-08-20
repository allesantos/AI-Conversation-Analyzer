from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.rag.in_memory_vector_store import InMemoryVectorStore
from app.conversation.types import MessageType
from app.core.config import Settings
from app.models.message import Message
from app.models.participant import Participant
from app.services.embedding import EmbeddingGenerationService
from app.services.embedding_enqueue import InlineEmbeddingJobEnqueuer


def build_embedding_service(
    session: AsyncSession,
    settings: Settings,
    fake_embeddings: FakeEmbeddingProvider,
    store: InMemoryVectorStore,
) -> EmbeddingGenerationService:
    service = EmbeddingGenerationService(
        session,
        settings,
        fake_embeddings,
        store,
        InlineEmbeddingJobEnqueuer(lambda _cid: None),
    )

    async def inline_generate(conversation_id: UUID) -> None:
        await service.generate_for_conversation(conversation_id)

    service.job_enqueuer = InlineEmbeddingJobEnqueuer(inline_generate)
    return service


async def seed_messages(
    session: AsyncSession,
    conversation_id: UUID,
    participant_id: UUID,
    count: int,
) -> None:
    base = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    rows: list[dict[str, object]] = []
    for index in range(count):
        rows.append(
            {
                "id": uuid4(),
                "conversation_id": conversation_id,
                "sender_id": participant_id,
                "timestamp": base + timedelta(minutes=index),
                "type": MessageType.TEXT.value,
                "content": f"Mensagem {index}" + ("?" if index % 17 == 0 else ""),
                "message_metadata": {},
                "created_at": datetime.now(UTC),
            }
        )
        if len(rows) >= 500:
            await session.execute(insert(Message), rows)
            rows.clear()
    if rows:
        await session.execute(insert(Message), rows)
    await session.commit()


async def create_conversation_with_messages(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str,
    message_count: int,
    session: AsyncSession,
) -> str:
    created = await client.post("/api/v1/conversations", headers=headers, json={"title": title})
    assert created.status_code == 201
    conversation_id = UUID(created.json()["id"])

    participant_id = uuid4()
    await session.execute(
        insert(Participant),
        [
            {
                "id": participant_id,
                "conversation_id": conversation_id,
                "name": "Ana",
                "role": "OWNER",
            }
        ],
    )
    await seed_messages(session, conversation_id, participant_id, message_count)
    return str(conversation_id)


async def open_test_session(app):
    from app.core.db import get_db

    generator = app.dependency_overrides[get_db]()
    return await generator.__anext__()

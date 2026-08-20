from collections.abc import AsyncGenerator
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.rag.in_memory_vector_store import InMemoryVectorStore
from app.api.deps import get_embedding_provider, get_embedding_service, get_vector_store
from app.core.config import Settings
from app.core.db import get_db
from app.main import create_app
from app.models import Base
from app.services.embedding import EmbeddingGenerationService
from app.services.embedding_enqueue import InlineEmbeddingJobEnqueuer

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def app() -> AsyncGenerator:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    application = create_app()

    fake_embeddings = FakeEmbeddingProvider()
    in_memory_store = InMemoryVectorStore()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

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

        async def inline_generate(conversation_id) -> None:
            await service.generate_for_conversation(conversation_id)

        service.job_enqueuer = InlineEmbeddingJobEnqueuer(inline_generate)
        return service

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    application.dependency_overrides[get_vector_store] = lambda _session: in_memory_store
    application.dependency_overrides[get_embedding_service] = override_embedding_service
    yield application

    application.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def auth_headers(
    client: AsyncClient, email: str, password: str = "password123"
) -> dict[str, str]:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "terms_accepted": True},
    )
    assert register.status_code == 201, register.text
    token = register.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.vector_store import EmbeddingRecord, VectorSearchResult, VectorStore
from app.models.embedding import MessageEmbedding


class PgVectorStore:
    """VectorStore backed by PostgreSQL + pgvector (HNSW index)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store(self, records: list[EmbeddingRecord]) -> int:
        if not records:
            return 0
        rows = [
            {
                "id": record.id or uuid4(),
                "conversation_id": record.conversation_id,
                "message_ids": [str(item) for item in record.message_ids],
                "chunk_text": record.chunk_text,
                "embedding": record.vector,
                "metadata": record.metadata,
            }
            for record in records
        ]
        await self.session.execute(insert(MessageEmbedding), rows)
        return len(rows)

    async def search(
        self,
        conversation_id: UUID,
        query_vector: list[float],
        *,
        top_k: int,
    ) -> list[VectorSearchResult]:
        vector_literal = _to_pgvector_literal(query_vector)
        stmt = text(
            """
            SELECT id, chunk_text, metadata,
                   1 - (embedding <=> :query_vector) AS score
            FROM message_embeddings
            WHERE conversation_id = :conversation_id
            ORDER BY embedding <=> :query_vector
            LIMIT :top_k
            """
        )
        result = await self.session.execute(
            stmt,
            {
                "conversation_id": conversation_id,
                "query_vector": vector_literal,
                "top_k": top_k,
            },
        )
        return [
            VectorSearchResult(
                id=row.id,
                chunk_text=row.chunk_text,
                score=float(row.score),
                metadata=row.metadata or {},
            )
            for row in result.mappings()
        ]

    async def delete_for_conversation(self, conversation_id: UUID) -> None:
        await self.session.execute(
            delete(MessageEmbedding).where(MessageEmbedding.conversation_id == conversation_id)
        )

    async def count_for_conversation(self, conversation_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(MessageEmbedding)
            .where(MessageEmbedding.conversation_id == conversation_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())


def _to_pgvector_literal(values: list[float]) -> str:
    joined = ",".join(f"{value:.8f}" for value in values)
    return f"[{joined}]"


def build_vector_store(session: AsyncSession) -> VectorStore:
    return PgVectorStore(session)

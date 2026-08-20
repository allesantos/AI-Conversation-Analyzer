from __future__ import annotations

import math
from uuid import UUID, uuid4

from app.ai.rag.vector_store import EmbeddingRecord, VectorSearchResult


class InMemoryVectorStore:
    """Implementação em memória para testes e ambientes sem pgvector."""

    def __init__(self) -> None:
        self._records: dict[UUID, list[EmbeddingRecord]] = {}

    async def store(self, records: list[EmbeddingRecord]) -> int:
        for record in records:
            bucket = self._records.setdefault(record.conversation_id, [])
            bucket.append(
                EmbeddingRecord(
                    id=record.id or uuid4(),
                    conversation_id=record.conversation_id,
                    message_ids=record.message_ids,
                    chunk_text=record.chunk_text,
                    vector=record.vector,
                    metadata=record.metadata,
                )
            )
        return len(records)

    async def search(
        self,
        conversation_id: UUID,
        query_vector: list[float],
        *,
        top_k: int,
    ) -> list[VectorSearchResult]:
        records = self._records.get(conversation_id, [])
        scored = [
            VectorSearchResult(
                id=record.id or uuid4(),
                chunk_text=record.chunk_text,
                score=_cosine_similarity(query_vector, record.vector),
                metadata=record.metadata,
            )
            for record in records
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    async def delete_for_conversation(self, conversation_id: UUID) -> None:
        self._records.pop(conversation_id, None)

    async def count_for_conversation(self, conversation_id: UUID) -> int:
        return len(self._records.get(conversation_id, []))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)

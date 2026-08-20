from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(slots=True, frozen=True)
class EmbeddingRecord:
    id: UUID | None
    conversation_id: UUID
    message_ids: list[UUID]
    chunk_text: str
    vector: list[float]
    metadata: dict[str, object]


@dataclass(slots=True, frozen=True)
class VectorSearchResult:
    id: UUID
    chunk_text: str
    score: float
    metadata: dict[str, object]


class VectorStore(Protocol):
    async def store(self, records: list[EmbeddingRecord]) -> int: ...

    async def search(
        self,
        conversation_id: UUID,
        query_vector: list[float],
        *,
        top_k: int,
    ) -> list[VectorSearchResult]: ...

    async def delete_for_conversation(self, conversation_id: UUID) -> None: ...

    async def count_for_conversation(self, conversation_id: UUID) -> int: ...

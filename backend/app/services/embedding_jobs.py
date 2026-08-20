from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class EmbeddingJobEnqueuer(Protocol):
    async def enqueue_generate_embeddings(self, conversation_id: UUID) -> None: ...


@dataclass(slots=True, frozen=True)
class EmbeddingReadiness:
    ready: bool
    status: str
    message: str

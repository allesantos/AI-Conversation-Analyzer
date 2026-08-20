from __future__ import annotations

from uuid import UUID

from app.ai.embeddings.provider import EmbeddingProvider
from app.ai.rag.vector_store import VectorSearchResult, VectorStore


class ConversationRetriever:
    def __init__(
        self,
        *,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        top_k: int,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.top_k = top_k

    async def retrieve(self, conversation_id: UUID, query: str) -> list[VectorSearchResult]:
        embedded = await self.embedding_provider.embed_texts([query])
        if not embedded.vectors:
            return []
        return await self.vector_store.search(
            conversation_id,
            embedded.vectors[0],
            top_k=self.top_k,
        )

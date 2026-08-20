from __future__ import annotations

from openai import AsyncOpenAI

from app.ai.embeddings.provider import EmbeddingResult, EmbeddingUsage


class OpenAIEmbeddingProvider:
    def __init__(self, *, api_key: str, model: str, dimensions: int = 1536) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[],
                usage=EmbeddingUsage(input_tokens=0, model=self._model, provider="openai"),
            )
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
            dimensions=self._dimensions,
        )
        vectors = [list(item.embedding) for item in response.data]
        tokens = response.usage.total_tokens if response.usage else 0
        return EmbeddingResult(
            vectors=vectors,
            usage=EmbeddingUsage(
                input_tokens=tokens,
                model=self._model,
                provider="openai",
            ),
        )

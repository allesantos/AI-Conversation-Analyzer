from __future__ import annotations

import hashlib
import math

from app.ai.embeddings.provider import EmbeddingResult, EmbeddingUsage

_FAKE_DIMENSIONS = 1536


class FakeEmbeddingProvider:
    """Embeddings determinísticos para testes — sem rede nem custo."""

    def __init__(self, *, dimensions: int = _FAKE_DIMENSIONS) -> None:
        self._dimensions = dimensions
        self.calls: list[list[str]] = []

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        self.calls.append(list(texts))
        vectors = [_hash_to_vector(text, self._dimensions) for text in texts]
        tokens = sum(max(1, len(text.split())) for text in texts)
        return EmbeddingResult(
            vectors=vectors,
            usage=EmbeddingUsage(
                input_tokens=tokens,
                model="fake-embedding",
                provider="fake",
            ),
        )


def _hash_to_vector(text: str, dimensions: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        block = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
        values.extend(byte / 255.0 for byte in block)
        counter += 1
    values = values[:dimensions]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]

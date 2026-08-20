from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class EmbeddingUsage:
    input_tokens: int
    model: str
    provider: str


@dataclass(slots=True, frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    usage: EmbeddingUsage


class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int: ...

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult: ...

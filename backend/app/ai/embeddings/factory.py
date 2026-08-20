from __future__ import annotations

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.embeddings.openai_provider import OpenAIEmbeddingProvider
from app.ai.embeddings.provider import EmbeddingProvider
from app.core.config import Settings
from app.core.exceptions import BadRequestError


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.strip().lower()
    if provider == "fake":
        return FakeEmbeddingProvider()
    if provider == "openai":
        if not settings.openai_api_key.strip():
            raise BadRequestError(
                "OPENAI_API_KEY não configurada. Adicione uma chave no .env para gerar embeddings."
            )
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
        )
    raise BadRequestError(f"Provedor de embeddings não suportado: {provider}")

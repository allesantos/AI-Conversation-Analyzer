from __future__ import annotations

from app.ai.llm.openai_provider import OpenAIProvider
from app.ai.llm.provider import LLMProvider
from app.core.config import Settings
from app.core.exceptions import BadRequestError


def build_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        if not settings.openai_api_key.strip():
            raise BadRequestError(
                "OPENAI_API_KEY não configurada. Adicione uma chave no .env para usar a IA."
            )
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
        )
    raise BadRequestError(f"Provedor LLM não suportado: {settings.llm_provider}")

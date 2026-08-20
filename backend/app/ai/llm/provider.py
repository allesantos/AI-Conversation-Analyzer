from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.ai.llm.types import LLMStructuredResult

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """Contrato desacoplado para provedores de LLM (OpenAI, Anthropic, Gemini)."""

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> LLMStructuredResult:
        """Gera saída estruturada validada por Pydantic."""
        ...

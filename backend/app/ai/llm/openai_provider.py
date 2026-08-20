from __future__ import annotations

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.ai.llm.types import LLMStructuredResult, LLMUsage


class OpenAIProvider:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> LLMStructuredResult:
        completion = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_model,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("Resposta do LLM não pôde ser validada")

        usage = completion.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        return LLMStructuredResult(
            data=parsed,
            usage=LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self._model,
                provider="openai",
            ),
        )

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.ai.llm.types import LLMStructuredResult, LLMUsage

T = TypeVar("T", bound=BaseModel)


class FakeLLMProvider:
    """Implementação determinística para testes — sem rede nem API key."""

    def __init__(
        self,
        *,
        summary_text: str = "Resumo fictício da conversa.",
        ask_text: str = "Resposta fictícia à pergunta.",
    ) -> None:
        self.summary_text = summary_text
        self.ask_text = ask_text
        self.calls: list[dict[str, object]] = []

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> LLMStructuredResult:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_model": response_model.__name__,
            }
        )
        payload = _build_payload(response_model, self.summary_text, self.ask_text)
        return LLMStructuredResult(
            data=response_model.model_validate(payload),
            usage=LLMUsage(
                input_tokens=100,
                output_tokens=50,
                model="fake-model",
                provider="fake",
            ),
        )


def _build_payload(model: type[BaseModel], summary_text: str, ask_text: str) -> dict[str, object]:
    name = model.__name__
    if name == "ConversationSummaryOutput":
        return {
            "summary": summary_text,
            "observations": ["Observação fictícia baseada nas métricas."],
            "inferences": ["Inferência fictícia com incerteza explícita."],
        }
    if name == "AskAnswerOutput":
        return {
            "answer": ask_text,
            "observations": ["Observação fictícia sobre o histórico."],
            "inferences": ["Inferência fictícia sobre a pergunta."],
        }
    if name == "ResponseSuggestionsOutput":
        return {
            "suggestions": [
                {"category": "NATURAL", "text": "Oi, tudo bem por aqui! E aí, como foi o dia?"},
                {"category": "DIVERTIDA", "text": "Haha boa! Conta mais, fiquei curiosa 😄"},
                {"category": "DIRETA", "text": "Entendi. Quando a gente se vê?"},
                {
                    "category": "CONSERVADORA",
                    "text": "Legal, bom saber. Qualquer coisa me fala!",
                },
            ]
        }
    raise ValueError(f"FakeLLMProvider não conhece o modelo {name}")

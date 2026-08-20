"""Centralised AI usage tracking. Call `record_*` from any service after an AI call."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.provider import EmbeddingUsage
from app.ai.llm.types import LLMUsage
from app.ai.transcription.provider import TranscriptionUsage
from app.models.ai_usage import AIUsage
from app.repositories.ai_usage import AIUsageRepository

# Rough cost per token/second (USD). Intentionally conservative.
_COST_PER_1K_INPUT: dict[str, float] = {
    "gpt-4o-mini": 0.00015,
    "text-embedding-3-small": 0.00002,
}
_COST_PER_1K_OUTPUT: dict[str, float] = {
    "gpt-4o-mini": 0.0006,
}
_COST_PER_MINUTE_AUDIO: dict[str, float] = {
    "whisper-1": 0.006,
}


def _estimate_llm_cost(usage: LLMUsage) -> float:
    inp = _COST_PER_1K_INPUT.get(usage.model, 0.0002) * usage.input_tokens / 1000
    out = _COST_PER_1K_OUTPUT.get(usage.model, 0.0008) * usage.output_tokens / 1000
    return round(inp + out, 6)


def _estimate_embedding_cost(usage: EmbeddingUsage) -> float:
    rate = _COST_PER_1K_INPUT.get(usage.model, 0.00002)
    return round(rate * usage.input_tokens / 1000, 6)


def _estimate_transcription_cost(usage: TranscriptionUsage) -> float:
    rate = _COST_PER_MINUTE_AUDIO.get(usage.model, 0.006)
    seconds = usage.duration_seconds or 0
    return round(rate * seconds / 60, 6)


async def record_llm_usage(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID | None,
    operation: str,
    usage: LLMUsage,
) -> AIUsage:
    repo = AIUsageRepository(session)
    return await repo.add(
        AIUsage(
            user_id=user_id,
            conversation_id=conversation_id,
            operation=operation,
            provider=usage.provider,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost=_estimate_llm_cost(usage),
        )
    )


async def record_embedding_usage(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID | None,
    operation: str,
    usage: EmbeddingUsage,
) -> AIUsage:
    repo = AIUsageRepository(session)
    return await repo.add(
        AIUsage(
            user_id=user_id,
            conversation_id=conversation_id,
            operation=operation,
            provider=usage.provider,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=0,
            estimated_cost=_estimate_embedding_cost(usage),
        )
    )


async def record_transcription_usage(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID | None,
    operation: str,
    usage: TranscriptionUsage,
) -> AIUsage:
    repo = AIUsageRepository(session)
    return await repo.add(
        AIUsage(
            user_id=user_id,
            conversation_id=conversation_id,
            operation=operation,
            provider=usage.provider,
            model=usage.model,
            input_tokens=0,
            output_tokens=0,
            audio_seconds=usage.duration_seconds,
            estimated_cost=_estimate_transcription_cost(usage),
        )
    )

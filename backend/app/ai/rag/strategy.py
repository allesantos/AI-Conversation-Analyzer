"""Decide qual estratégia de contexto usar conforme o tamanho da conversa."""

from __future__ import annotations

from app.ai.rag.types import ContextStrategy
from app.core.config import Settings


def determine_context_strategy(message_count: int, settings: Settings) -> ContextStrategy:
    if message_count <= settings.rag_direct_max_messages:
        return ContextStrategy.DIRECT
    if message_count <= settings.rag_summary_max_messages:
        return ContextStrategy.SUMMARY_SELECTION
    return ContextStrategy.RAG

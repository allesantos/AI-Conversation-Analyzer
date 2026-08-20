"""Monta contexto textual para análise direta (sem RAG)."""

from __future__ import annotations

import json
from datetime import timedelta

from app.ai.rag.vector_store import VectorSearchResult
from app.conversation.metric_message import MetricMessage
from app.conversation.metrics import DEFAULT_GAP_HOURS
from app.conversation.types import MessageType
from app.core.config import Settings

_MAX_SNIPPET_CHARS = 240


def build_direct_context(
    messages: list[MetricMessage],
    *,
    max_messages: int,
) -> str:
    ordered = sorted(messages, key=lambda item: (item.timestamp, str(item.id)))
    if len(ordered) > max_messages:
        msg = (
            f"A conversa possui {len(ordered)} mensagens, acima do limite de "
            f"{max_messages} para análise direta."
        )
        raise ValueError(msg)

    return _format_messages(ordered)


def select_intermediate_messages(
    messages: list[MetricMessage],
    settings: Settings,
    *,
    gap_hours: float = DEFAULT_GAP_HOURS,
) -> list[MetricMessage]:
    """Seleciona mensagens recentes + perguntas + inícios de conversa para faixa 2k-10k."""
    ordered = sorted(messages, key=lambda item: (item.timestamp, str(item.id)))
    analyzable = [item for item in ordered if item.message_type != MessageType.SYSTEM]
    if not analyzable:
        return []

    selected: dict[str, MetricMessage] = {}

    for item in analyzable[-settings.rag_intermediate_recent_messages :]:
        selected[str(item.id)] = item

    for item in analyzable:
        if item.content.strip().endswith("?"):
            selected[str(item.id)] = item

    gap = timedelta(hours=gap_hours)
    previous: MetricMessage | None = None
    for item in analyzable:
        if previous is None or item.timestamp - previous.timestamp > gap:
            selected[str(item.id)] = item
        previous = item

    capped = sorted(selected.values(), key=lambda item: (item.timestamp, str(item.id)))
    return capped[-settings.rag_intermediate_max_messages :]


def build_intermediate_context(
    messages: list[MetricMessage],
    settings: Settings,
) -> str:
    selected = select_intermediate_messages(messages, settings)
    header = f"Contexto selecionado ({len(selected)} mensagens de {len(messages)} totais):\n"
    return header + _format_messages(selected)


def build_rag_context(
    *,
    metrics: dict[str, object],
    summary: str | None,
    retrieved: list[VectorSearchResult],
) -> str:
    parts = [
        "Métricas objetivas (JSON):",
        json.dumps(metrics, ensure_ascii=False, indent=2),
    ]
    if summary:
        parts.extend(["", "Resumo da conversa:", summary])
    if retrieved:
        parts.extend(["", "Trechos recuperados por similaridade:"])
        for index, item in enumerate(retrieved, start=1):
            parts.append(f"[{index}] (score={item.score:.3f}) {item.chunk_text}")
    else:
        parts.append("\nNenhum trecho recuperado.")
    return "\n".join(parts)


def _format_messages(messages: list[MetricMessage]) -> str:
    lines: list[str] = []
    for item in messages:
        if item.message_type == MessageType.SYSTEM:
            label = "Sistema"
            snippet = _snippet(item.content)
            lines.append(f"[{item.timestamp.isoformat()}] {label}: {snippet}")
            continue
        sender = item.sender_name or "Desconhecido"
        snippet = _snippet(item.content)
        lines.append(f"[{item.timestamp.isoformat()}] {sender}: {snippet}")
    return "\n".join(lines)


def _snippet(content: str) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= _MAX_SNIPPET_CHARS:
        return normalized
    return normalized[: _MAX_SNIPPET_CHARS - 3] + "..."

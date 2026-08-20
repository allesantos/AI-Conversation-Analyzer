"""Métricas objetivas calculadas em Python puro, sem LLM."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import Any

from app.conversation.metric_message import MetricMessage
from app.conversation.types import MessageType

DEFAULT_GAP_HOURS = 4


@dataclass(slots=True, frozen=True)
class ResponseTimeStats:
    count: int
    average_seconds: float | None
    median_seconds: float | None
    min_seconds: float | None
    max_seconds: float | None


def calculate_conversation_metrics(
    messages: list[MetricMessage],
    *,
    gap_hours: float = DEFAULT_GAP_HOURS,
) -> dict[str, Any]:
    """Calcula métricas objetivas para uma conversa importada."""
    if not messages:
        return _empty_metrics()

    ordered = sorted(messages, key=lambda item: (item.timestamp, str(item.id)))
    analyzable = [item for item in ordered if item.message_type != MessageType.SYSTEM]
    participants = _participant_names(analyzable)

    counts_by_participant = Counter(
        item.sender_name or "Desconhecido" for item in analyzable if item.sender_name
    )
    total_analyzable = len(analyzable)
    initiations = _conversation_initiations(analyzable, gap_hours=gap_hours)
    response_stats = _response_time_stats(analyzable)
    question_counts = _question_counts(analyzable)
    media_counts = _media_counts(ordered)
    frequency = _frequency(ordered)

    proportions: dict[str, float] = {}
    if total_analyzable:
        for name, count in counts_by_participant.items():
            proportions[name] = round(count / total_analyzable, 4)

    avg_lengths: dict[str, float] = {}
    length_groups: dict[str, list[int]] = defaultdict(list)
    for item in analyzable:
        if not item.sender_name:
            continue
        # MEDIA_OCULTA é um placeholder repetitivo do WhatsApp; ignoramos para
        # métricas baseadas em "conteúdo textual" (comprimento médio etc.).
        if item.message_type == MessageType.MEDIA_OCULTA:
            continue
        length_groups[item.sender_name].append(len(item.content.strip()))
    for name, lengths in length_groups.items():
        avg_lengths[name] = round(statistics.mean(lengths), 2) if lengths else 0.0

    return {
        "total_messages": len(ordered),
        "total_analyzable_messages": total_analyzable,
        "total_system_messages": len(ordered) - total_analyzable,
        "participants": participants,
        "messages_by_participant": dict(counts_by_participant),
        "message_proportion_by_participant": proportions,
        "average_message_length_by_participant": avg_lengths,
        "conversation_initiations": initiations,
        "response_time_seconds": {
            "count": response_stats.count,
            "average": response_stats.average_seconds,
            "median": response_stats.median_seconds,
            "min": response_stats.min_seconds,
            "max": response_stats.max_seconds,
        },
        "questions_by_participant": question_counts,
        "media_counts": media_counts,
        "frequency": frequency,
        "period": {
            "first_message_at": ordered[0].timestamp.isoformat(),
            "last_message_at": ordered[-1].timestamp.isoformat(),
        },
        "settings": {"conversation_gap_hours": gap_hours},
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_messages": 0,
        "total_analyzable_messages": 0,
        "total_system_messages": 0,
        "participants": [],
        "messages_by_participant": {},
        "message_proportion_by_participant": {},
        "average_message_length_by_participant": {},
        "conversation_initiations": {},
        "response_time_seconds": {
            "count": 0,
            "average": None,
            "median": None,
            "min": None,
            "max": None,
        },
        "questions_by_participant": {},
        "media_counts": {"audio": 0, "image": 0, "text": 0},
        "frequency": {"messages_per_day": {}, "messages_per_week": {}},
        "period": {"first_message_at": None, "last_message_at": None},
        "settings": {"conversation_gap_hours": DEFAULT_GAP_HOURS},
    }


def _participant_names(messages: list[MetricMessage]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in messages:
        if item.sender_name and item.sender_name not in seen:
            seen.add(item.sender_name)
            ordered.append(item.sender_name)
    return ordered


def _conversation_initiations(
    messages: list[MetricMessage],
    *,
    gap_hours: float,
) -> dict[str, int]:
    if not messages:
        return {}
    gap = timedelta(hours=gap_hours)
    counts: Counter[str] = Counter()
    previous: MetricMessage | None = None
    for item in messages:
        if not item.sender_name:
            continue
        if previous is None or item.timestamp - previous.timestamp > gap:
            counts[item.sender_name] += 1
        previous = item
    return dict(counts)


def _response_time_stats(messages: list[MetricMessage]) -> ResponseTimeStats:
    deltas: list[float] = []
    previous: MetricMessage | None = None
    for item in messages:
        if not item.sender_name:
            continue
        if (
            previous is not None
            and previous.sender_name
            and previous.sender_name != item.sender_name
        ):
            delta = (item.timestamp - previous.timestamp).total_seconds()
            if delta >= 0:
                deltas.append(delta)
        previous = item

    if not deltas:
        return ResponseTimeStats(0, None, None, None, None)

    return ResponseTimeStats(
        count=len(deltas),
        average_seconds=round(statistics.mean(deltas), 2),
        median_seconds=round(statistics.median(deltas), 2),
        min_seconds=round(min(deltas), 2),
        max_seconds=round(max(deltas), 2),
    )


def _question_counts(messages: list[MetricMessage]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in messages:
        if not item.sender_name:
            continue
        if item.message_type == MessageType.MEDIA_OCULTA:
            continue
        stripped = item.content.strip()
        if stripped.endswith("?"):
            counts[item.sender_name] += 1
    return dict(counts)


def _media_counts(messages: list[MetricMessage]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in messages:
        if item.message_type == MessageType.AUDIO:
            counts["audio"] += 1
        elif item.message_type == MessageType.IMAGE:
            counts["image"] += 1
        elif item.message_type in {MessageType.TEXT, MessageType.MEDIA_OCULTA}:
            counts["text"] += 1
    return {
        "audio": counts.get("audio", 0),
        "image": counts.get("image", 0),
        "text": counts.get("text", 0),
    }


def _frequency(messages: list[MetricMessage]) -> dict[str, dict[str, int]]:
    per_day: Counter[str] = Counter()
    per_week: Counter[str] = Counter()
    for item in messages:
        day = item.timestamp.astimezone(UTC).date().isoformat()
        per_day[day] += 1
        year, week, _ = item.timestamp.isocalendar()
        per_week[f"{year}-W{week:02d}"] += 1
    return {
        "messages_per_day": dict(sorted(per_day.items())),
        "messages_per_week": dict(sorted(per_week.items())),
    }

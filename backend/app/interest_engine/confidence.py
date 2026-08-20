from __future__ import annotations

from datetime import datetime
from typing import Any

from app.interest_engine.types import ClassifiedSignal
from app.interest_engine.weights import (
    CONFIDENCE_FULL_MESSAGE_COUNT,
    CONFIDENCE_FULL_SIGNAL_COUNT,
    CONFIDENCE_FULL_SPAN_DAYS,
    CONFIDENCE_LOW_VOLUME_CAP,
    CONFIDENCE_LOW_VOLUME_MESSAGE_THRESHOLD,
)


def calculate_confidence_score(
    metrics: dict[str, Any],
    signals: list[ClassifiedSignal],
) -> int:
    """Confiança baseada em volume, span temporal e quantidade de sinais com evidência."""
    total_messages = int(metrics.get("total_analyzable_messages", 0))
    period = metrics.get("period", {})
    first_raw = period.get("first_message_at")
    last_raw = period.get("last_message_at")

    span_days = 0.0
    if first_raw and last_raw:
        first = datetime.fromisoformat(str(first_raw))
        last = datetime.fromisoformat(str(last_raw))
        span_days = max(0.0, (last - first).total_seconds() / 86400)

    signals_with_evidence = [item for item in signals if item.message_ids]
    message_factor = min(1.0, total_messages / CONFIDENCE_FULL_MESSAGE_COUNT)
    span_factor = min(1.0, span_days / CONFIDENCE_FULL_SPAN_DAYS) if span_days else 0.2
    signal_factor = min(1.0, len(signals_with_evidence) / CONFIDENCE_FULL_SIGNAL_COUNT)

    raw = message_factor * 0.45 + span_factor * 0.25 + signal_factor * 0.30
    confidence = int(round(raw * 100))

    if total_messages < CONFIDENCE_LOW_VOLUME_MESSAGE_THRESHOLD:
        confidence = min(confidence, CONFIDENCE_LOW_VOLUME_CAP)

    return max(0, min(100, confidence))

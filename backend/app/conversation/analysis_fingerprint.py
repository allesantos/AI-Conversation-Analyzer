from __future__ import annotations

import hashlib
from datetime import UTC

from app.conversation.metric_message import MetricMessage


def _utc_iso(timestamp) -> str:
    if timestamp.tzinfo is None:
        aware = timestamp.replace(tzinfo=UTC)
    else:
        aware = timestamp.astimezone(UTC)
    return aware.replace(microsecond=0).isoformat()


def compute_analysis_fingerprint(messages: list[MetricMessage]) -> str:
    """Hash estável do conteúdo analisável (ignora IDs — sobrevive a reimportações)."""
    lines: list[str] = []
    for item in sorted(
        messages,
        key=lambda message: (
            message.timestamp.astimezone(UTC)
            if message.timestamp.tzinfo
            else message.timestamp.replace(tzinfo=UTC),
            message.sender_name or "",
            message.message_type.value,
            message.content,
        ),
    ):
        lines.append(
            "|".join(
                [
                    _utc_iso(item.timestamp),
                    item.message_type.value,
                    item.sender_name or "",
                    item.content,
                ]
            )
        )
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

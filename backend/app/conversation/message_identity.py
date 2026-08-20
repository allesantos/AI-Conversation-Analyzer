"""Chave estável de identidade de mensagem para dedupe em reimport."""

from __future__ import annotations

from datetime import UTC, datetime


def _utc_iso(timestamp: datetime) -> str:
    """Normaliza para UTC — evita falha de dedupe entre -03:00 e +00:00."""
    if timestamp.tzinfo is None:
        aware = timestamp.replace(tzinfo=UTC)
    else:
        aware = timestamp.astimezone(UTC)
    return aware.replace(microsecond=0).isoformat()


def message_identity_key(
    *,
    timestamp: datetime,
    message_type: str,
    sender_name: str | None,
    content: str,
) -> str:
    """Mesmos campos semânticos do fingerprint de análise (sem IDs)."""
    return "|".join(
        [
            _utc_iso(timestamp),
            message_type,
            sender_name or "",
            content,
        ]
    )


def attachment_identity_key(
    *,
    timestamp: datetime,
    sender_name: str | None,
) -> str:
    """Chave secundária para mídia/áudio — sobrevive à troca de content na transcrição."""
    return f"{_utc_iso(timestamp)}|{sender_name or ''}|__ATTACHMENT__"


_ATTACHMENT_TYPES = frozenset({"AUDIO", "MEDIA_OCULTA", "IMAGE", "VIDEO", "DOCUMENT"})


def is_attachment_message(*, message_type: str, metadata: dict | None = None) -> bool:
    if message_type in _ATTACHMENT_TYPES:
        return True
    if isinstance(metadata, dict) and (
        metadata.get("attachment") is True or metadata.get("transcribed") is True
    ):
        return True
    return False

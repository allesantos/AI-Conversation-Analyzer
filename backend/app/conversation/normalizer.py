"""Converte ParsedMessage no modelo de participantes e mensagens da aplicação."""

from __future__ import annotations

from collections.abc import Iterable

from app.conversation.dto import NormalizedMessage, NormalizedParticipant, ParsedMessage
from app.conversation.types import ParticipantRole

_MAX_PARTICIPANT_NAME = 200


class ConversationNormalizer:
    """Acumula participantes e normaliza mensagens uma a uma (streaming)."""

    def __init__(self, owner_name: str | None = None) -> None:
        trimmed = owner_name.strip() if owner_name else ""
        self._owner_name = trimmed or None
        self.participants: dict[str, NormalizedParticipant] = {}

    def normalize_message(self, parsed: ParsedMessage) -> NormalizedMessage:
        sender_name = None
        if parsed.sender_name:
            sender_name = parsed.sender_name[:_MAX_PARTICIPANT_NAME]
            self._ensure_participant(sender_name)
        return NormalizedMessage(
            sender_name=sender_name,
            timestamp=parsed.timestamp,
            message_type=parsed.message_type,
            content=parsed.content,
            metadata=dict(parsed.metadata),
        )

    def normalize_all(
        self, messages: Iterable[ParsedMessage]
    ) -> tuple[list[NormalizedParticipant], list[NormalizedMessage]]:
        normalized = [self.normalize_message(message) for message in messages]
        return list(self.participants.values()), normalized

    def _ensure_participant(self, name: str) -> None:
        key = name[:_MAX_PARTICIPANT_NAME]
        if key in self.participants:
            return
        role = ParticipantRole.OTHER
        if self._owner_name and key.casefold() == self._owner_name.casefold():
            role = ParticipantRole.OWNER
        self.participants[key] = NormalizedParticipant(name=key, role=role)

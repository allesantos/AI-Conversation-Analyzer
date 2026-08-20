from __future__ import annotations

from app.conversation.types import ParticipantRole
from app.models.participant import Participant


def resolve_analysis_participants(
    participants: list[Participant],
) -> tuple[str, str]:
    """Retorna (owner_name, other_name) para análise de interesse."""
    owner = next((item for item in participants if item.role == ParticipantRole.OWNER.value), None)
    other = next((item for item in participants if item.role == ParticipantRole.OTHER.value), None)
    if owner and other:
        return owner.name, other.name
    if len(participants) >= 2:
        return participants[0].name, participants[1].name
    if len(participants) == 1:
        return participants[0].name, participants[0].name
    return "Participante A", "Participante B"

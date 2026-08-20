from enum import StrEnum


class MessageType(StrEnum):
    TEXT = "TEXT"
    MEDIA_OCULTA = "MEDIA_OCULTA"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    SYSTEM = "SYSTEM"


class ParticipantRole(StrEnum):
    OWNER = "OWNER"
    OTHER = "OTHER"

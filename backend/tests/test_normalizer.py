from app.conversation.normalizer import ConversationNormalizer
from app.conversation.types import MessageType, ParticipantRole
from app.conversation.whatsapp_parser import WhatsAppParser


def test_normalizer_assigns_owner_role_case_insensitive() -> None:
    parser = WhatsAppParser()
    messages = parser.parse_lines(
        [
            "18/08/2026 09:15 - Marina Costa: Oi",
            "18/08/2026 09:16 - Pedro Almeida: Oi",
            "18/08/2026 09:17 - As mensagens e as ligações são protegidas "
            "com a criptografia de ponta a ponta.",
        ]
    )
    normalizer = ConversationNormalizer(owner_name="marina costa")
    participants, normalized = normalizer.normalize_all(messages)

    names = {item.name: item.role for item in participants}
    assert names["Marina Costa"] == ParticipantRole.OWNER
    assert names["Pedro Almeida"] == ParticipantRole.OTHER
    assert len(participants) == 2
    assert normalized[2].message_type == MessageType.SYSTEM
    assert normalized[2].sender_name is None

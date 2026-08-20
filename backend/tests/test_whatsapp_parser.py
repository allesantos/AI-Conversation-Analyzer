from datetime import UTC
from pathlib import Path

from app.conversation.types import MessageType
from app.conversation.whatsapp_parser import WhatsAppParser

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp"


def _parse(name: str) -> tuple[list, WhatsAppParser]:
    parser = WhatsAppParser()
    path = FIXTURES / name
    messages = list(parser.parse_file(path))
    return messages, parser


def test_parser_module_is_decoupled() -> None:
    source = Path("app/conversation/whatsapp_parser.py").read_text(encoding="utf-8")
    assert "fastapi" not in source
    assert "sqlalchemy" not in source
    assert "UploadFile" not in source


def test_standard_oneline() -> None:
    messages, parser = _parse("standard_oneline.txt")
    assert parser.skipped_line_count == 0
    assert len(messages) == 3
    assert messages[0].sender_name == "Marina Costa"
    assert messages[0].content == "Oi Pedro, tudo bem?"
    assert messages[0].message_type == MessageType.TEXT
    assert messages[0].timestamp.day == 18
    assert messages[0].timestamp.hour == 9
    assert messages[0].timestamp.minute == 15
    assert messages[0].timestamp.second == 0
    assert messages[1].sender_name == "Pedro Almeida"
    assert messages[2].content == "Também. Vamos marcar aquele café?"


def test_multiline_and_seconds() -> None:
    messages, parser = _parse("multiline.txt")
    assert parser.skipped_line_count == 0
    assert len(messages) == 3
    assert messages[0].content == (
        "Segue o endereço:\nRua das Palmeiras, 120\nApto 45\nPerto da padaria."
    )
    assert messages[1].sender_name == "Pedro Almeida"
    assert messages[2].timestamp.second == 15


def test_system_messages_have_no_sender() -> None:
    messages, parser = _parse("system.txt")
    assert parser.skipped_line_count == 0
    assert len(messages) == 4
    assert messages[0].message_type == MessageType.SYSTEM
    assert messages[0].sender_name is None
    assert "criptografia de ponta a ponta" in messages[0].content
    assert messages[1].message_type == MessageType.SYSTEM
    assert messages[1].sender_name is None
    assert messages[1].content == "Você adicionou Pedro Almeida"
    assert messages[2].message_type == MessageType.SYSTEM
    assert messages[3].message_type == MessageType.TEXT
    assert messages[3].sender_name == "Marina Costa"


def test_attachments() -> None:
    messages, _parser = _parse("attachments.txt")
    assert messages[0].message_type == MessageType.IMAGE
    assert messages[0].metadata["filename"] == "foto_praia.jpg"
    assert messages[1].message_type == MessageType.MEDIA_OCULTA
    assert messages[1].metadata["hidden_media"] is True
    assert messages[2].message_type == MessageType.AUDIO
    assert messages[2].metadata["filename"] == "PTT-20260818-WA0001.opus"
    assert messages[3].message_type == MessageType.TEXT
    assert messages[3].metadata["filename"] == "notas.pdf"


def test_hidden_media_variants_are_media_oculta() -> None:
    messages_old, _ = _parse("attachments.txt")
    hidden_old = next(item for item in messages_old if item.metadata.get("hidden_media") is True)
    assert hidden_old.message_type == MessageType.MEDIA_OCULTA

    parser = WhatsAppParser()
    messages_new = list(parser.parse_file(FIXTURES / "hidden_media_new.txt"))
    hidden_new = next(item for item in messages_new if item.metadata.get("hidden_media") is True)
    assert hidden_new.message_type == MessageType.MEDIA_OCULTA


def test_emojis_accents_and_names_with_spaces() -> None:
    messages, _parser = _parse("emojis_accents.txt")
    assert messages[0].sender_name == "José da Silva"
    assert "😄" in messages[0].content
    assert "açaí" in messages[1].content
    assert messages[2].content == "Você viu o João Pedro ontem?"

    named, parser = _parse("names_with_spaces.txt")
    assert parser.skipped_line_count == 0
    assert named[0].sender_name == "Maria Clara Nogueira"
    assert named[1].sender_name == "João Pedro Almeida"


def test_malformed_lines_are_skipped_and_import_continues() -> None:
    messages, parser = _parse("malformed.txt")
    assert parser.skipped_line_count == 3
    assert len(messages) == 2
    assert messages[0].content == "Primeira mensagem válida."
    assert messages[1].content == "Segunda mensagem válida."
    assert messages[1].sender_name == "Pedro Almeida"


def test_empty_and_single_message() -> None:
    empty, empty_parser = _parse("empty.txt")
    assert empty == []
    assert empty_parser.skipped_line_count == 0

    single, parser = _parse("single_message.txt")
    assert parser.skipped_line_count == 0
    assert len(single) == 1
    assert single[0].content == "Só esta mensagem."


def test_orphan_only_file_does_not_raise() -> None:
    messages, parser = _parse("orphan_only.txt")
    assert messages == []
    assert parser.skipped_line_count == 2


def test_direction_mark_is_stripped() -> None:
    parser = WhatsAppParser()
    line = "\u200e18/08/2026 09:15 - Marina Costa: com marca"
    messages = list(parser.parse_lines([line]))
    assert len(messages) == 1
    assert messages[0].sender_name == "Marina Costa"
    assert messages[0].content == "com marca"


def test_streaming_from_generator() -> None:
    parser = WhatsAppParser()

    def lines():
        yield "18/08/2026 09:15 - Marina Costa: uma"
        yield "18/08/2026 09:16 - Pedro Almeida: duas"

    messages = list(parser.parse_lines(lines()))
    assert [item.content for item in messages] == ["uma", "duas"]


def test_ios_brackets_two_and_four_digit_years() -> None:
    messages, parser = _parse("ios_brackets.txt")
    assert parser.skipped_line_count == 0
    assert len(messages) == 5
    assert messages[0].message_type == MessageType.SYSTEM
    assert messages[0].sender_name is None
    assert messages[0].timestamp.year == 2026
    assert messages[1].sender_name == "Marina Costa"
    assert messages[1].content == "Oi Pedro, tudo bem?"
    assert messages[1].timestamp.second == 3
    assert messages[2].content == "Oi Marina! Segue o endereço:\nRua das Palmeiras, 120\nApto 45"
    assert messages[3].message_type == MessageType.IMAGE
    assert messages[3].metadata["filename"] == "foto_praia.jpg"
    assert messages[3].timestamp.year == 2026
    assert messages[4].sender_name == "Pedro Almeida"
    assert messages[4].content == "Recebi, obrigado!"


def test_ios_direction_mark_is_stripped() -> None:
    parser = WhatsAppParser()
    line = "\u200e[18/08/26, 09:15:03] Marina Costa: com marca"
    messages = list(parser.parse_lines([line]))
    assert len(messages) == 1
    assert messages[0].sender_name == "Marina Costa"
    assert messages[0].timestamp.year == 2026


def test_bracket_line_in_android_file_is_multiline_not_header() -> None:
    parser = WhatsAppParser()
    messages = list(
        parser.parse_lines(
            [
                "18/08/2026 09:15 - Marina Costa: Olha este trecho:",
                "[18/08/26, 09:16:03] Pedro Almeida: isso não é um cabeçalho iOS",
                "18/08/2026 09:17 - Pedro Almeida: Continuando no Android",
            ]
        )
    )
    assert len(messages) == 2
    assert messages[0].sender_name == "Marina Costa"
    ios_as_body = "[18/08/26, 09:16:03] Pedro Almeida: isso não é um cabeçalho iOS"
    assert ios_as_body in messages[0].content
    assert messages[1].sender_name == "Pedro Almeida"
    assert messages[1].content == "Continuando no Android"


def test_dash_line_in_ios_file_is_multiline_not_header() -> None:
    parser = WhatsAppParser()
    messages = list(
        parser.parse_lines(
            [
                "[18/08/26, 09:15:03] Marina Costa: Olha este trecho:",
                "18/08/2026 09:16 - Pedro Almeida: isso não é um cabeçalho Android",
                "[18/08/26, 09:17:00] Pedro Almeida: Continuando no iOS",
            ]
        )
    )
    assert len(messages) == 2
    assert messages[0].sender_name == "Marina Costa"
    android_as_body = "18/08/2026 09:16 - Pedro Almeida: isso não é um cabeçalho Android"
    assert android_as_body in messages[0].content
    assert messages[1].sender_name == "Pedro Almeida"
    assert messages[1].content == "Continuando no iOS"


def test_timestamp_uses_brazil_timezone() -> None:
    parser = WhatsAppParser()
    messages = list(parser.parse_lines(["18/08/2026 09:15 - Ana: Bom dia"]))
    ts = messages[0].timestamp
    assert ts.tzinfo is not None
    utc_ts = ts.astimezone(UTC)
    assert utc_ts.hour == 12
    assert utc_ts.minute == 15

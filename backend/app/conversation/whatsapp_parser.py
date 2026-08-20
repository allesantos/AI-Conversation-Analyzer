"""Parser de export .txt do WhatsApp (formatos brasileiros Android e iOS).

Desacoplado de FastAPI, banco e sessão. Consome linhas em streaming.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

from app.conversation.dto import ParsedMessage
from app.conversation.media import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS
from app.conversation.types import MessageType

logger = logging.getLogger("app.conversation.parser")

ANDROID_HEADER_RE = re.compile(r"^(\d{2}/\d{2}/\d{4}) (\d{2}:\d{2}(?::\d{2})?) - (.*)$")
IOS_HEADER_RE = re.compile(r"^\[(\d{2}/\d{2}/(?:\d{4}|\d{2})), (\d{2}:\d{2}:\d{2})\] (.*)$")
ATTACHED_RE = re.compile(r"^(.+?) \(arquivo anexado\)$", re.IGNORECASE)
HIDDEN_MEDIA_OLD = "<arquivo de mídia oculto>"
HIDDEN_MEDIA_NEW = "<mídia oculta>"

_DIRECTION_MARKS = "\ufeff\u200e\u200f"
_BR_TZ = ZoneInfo("America/Sao_Paulo")


class _ExportFormat(StrEnum):
    ANDROID = "android"
    IOS = "ios"


class WhatsAppParser:
    """Analisa exports Android (traço) e iOS (colchetes), detectados automaticamente."""

    def __init__(self) -> None:
        self.skipped_line_count = 0
        self._format: _ExportFormat | None = None

    def parse_file(self, path: Path) -> Iterator[ParsedMessage]:
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
            yield from self.parse_lines(handle)

    def parse_lines(self, lines: Iterable[str]) -> Iterator[ParsedMessage]:
        self.skipped_line_count = 0
        self._format = None
        current: ParsedMessage | None = None

        for line_number, raw in enumerate(lines, start=1):
            line = _clean_line(raw)
            if not line:
                if current is not None:
                    current = _append_content(current, "")
                continue

            parsed_header = self._try_parse_header(line, line_number)
            if parsed_header is _INVALID_HEADER:
                self._skip(line_number, "invalid_datetime")
                continue
            if parsed_header is not None:
                if current is not None:
                    yield current
                current = parsed_header
                continue

            if current is None:
                self._skip(line_number, "orphan_line")
                continue
            current = _append_content(current, line)

        if current is not None:
            yield current

    def _try_parse_header(self, line: str, line_number: int) -> ParsedMessage | None | object:
        matched = self._match_header(line)
        if matched is None:
            return None
        match, fmt = matched
        date_str, time_str, remainder = match.groups()
        timestamp = _parse_timestamp(date_str, time_str)
        if timestamp is None:
            return _INVALID_HEADER
        self._format = fmt
        return _build_message(timestamp, remainder, line_number)

    def _match_header(self, line: str) -> tuple[re.Match[str], _ExportFormat] | None:
        if self._format is _ExportFormat.ANDROID:
            match = ANDROID_HEADER_RE.match(line)
            return (match, _ExportFormat.ANDROID) if match else None
        if self._format is _ExportFormat.IOS:
            match = IOS_HEADER_RE.match(line)
            return (match, _ExportFormat.IOS) if match else None
        ios_match = IOS_HEADER_RE.match(line)
        if ios_match:
            return ios_match, _ExportFormat.IOS
        android_match = ANDROID_HEADER_RE.match(line)
        if android_match:
            return android_match, _ExportFormat.ANDROID
        return None

    def _skip(self, line_number: int, reason: str) -> None:
        self.skipped_line_count += 1
        logger.warning(
            "skipped_whatsapp_line line_number=%s reason=%s",
            line_number,
            reason,
        )


_INVALID_HEADER = object()


def _clean_line(raw: str) -> str:
    return raw.rstrip("\r\n").lstrip(_DIRECTION_MARKS).rstrip()


def _parse_timestamp(date_str: str, time_str: str) -> datetime | None:
    year_part = date_str.rsplit("/", 1)[-1]
    date_fmt = "%d/%m/%y" if len(year_part) == 2 else "%d/%m/%Y"
    time_fmt = "%H:%M:%S" if time_str.count(":") == 2 else "%H:%M"
    try:
        parsed = datetime.strptime(f"{date_str} {time_str}", f"{date_fmt} {time_fmt}")
    except ValueError:
        return None
    return parsed.replace(tzinfo=_BR_TZ)


def _build_message(timestamp: datetime, remainder: str, line_number: int) -> ParsedMessage:
    if ": " not in remainder:
        return ParsedMessage(
            timestamp=timestamp,
            sender_name=None,
            content=remainder,
            message_type=MessageType.SYSTEM,
            metadata={},
            line_number=line_number,
        )
    sender, content = remainder.split(": ", 1)
    message_type, metadata = classify_content(content)
    return ParsedMessage(
        timestamp=timestamp,
        sender_name=sender.strip() or None,
        content=content,
        message_type=message_type if sender.strip() else MessageType.SYSTEM,
        metadata=metadata,
        line_number=line_number,
    )


def classify_content(content: str) -> tuple[MessageType, dict[str, object]]:
    stripped = content.strip().lstrip(_DIRECTION_MARKS).strip()
    lowered = stripped.casefold()

    if lowered in {HIDDEN_MEDIA_OLD.casefold(), HIDDEN_MEDIA_NEW.casefold()}:
        return MessageType.MEDIA_OCULTA, {"attachment": True, "hidden_media": True}

    attached = ATTACHED_RE.match(stripped)
    if attached is not None:
        filename = attached.group(1)
        return _type_from_filename(filename), {
            "attachment": True,
            "filename": filename,
        }

    return MessageType.TEXT, {}


def _type_from_filename(filename: str) -> MessageType:
    lower = filename.lower()
    dot = lower.rfind(".")
    extension = lower[dot:] if dot >= 0 else ""
    if extension in IMAGE_EXTENSIONS:
        return MessageType.IMAGE
    if extension in AUDIO_EXTENSIONS:
        return MessageType.AUDIO
    prefix = lower.split("-", 1)[0]
    if prefix in {"img", "stk"}:
        return MessageType.IMAGE
    if prefix in {"ptt", "aud"}:
        return MessageType.AUDIO
    return MessageType.TEXT


def _append_content(message: ParsedMessage, extra_line: str) -> ParsedMessage:
    if extra_line == "":
        new_content = f"{message.content}\n"
    else:
        new_content = f"{message.content}\n{extra_line}"
    return ParsedMessage(
        timestamp=message.timestamp,
        sender_name=message.sender_name,
        content=new_content,
        message_type=message.message_type,
        metadata=message.metadata,
        line_number=message.line_number,
    )

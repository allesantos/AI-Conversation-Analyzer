"""Matching de arquivos de áudio do export WhatsApp → mensagens MEDIA_OCULTA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

BATCH_MATCH_TOLERANCE_SECONDS = 5 * 60
WHATSAPP_FILENAME_RE = re.compile(r"^(PTT|AUD|IMG|VID)-(\d{8})-WA(\d+)\.", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class AudioMatchCandidate:
    message_id: UUID
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class ZipAudioInput:
    file_key: str
    filename: str
    modified_ms: int


@dataclass(frozen=True, slots=True)
class AudioMatchResult:
    message_id: UUID
    diff_seconds: float
    matched_by_filename_fallback: bool = False


def parse_whatsapp_filename_date(filename: str) -> str | None:
    match = WHATSAPP_FILENAME_RE.match(filename)
    if match is None:
        return None
    raw = match.group(2)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def parse_whatsapp_filename_sequence(filename: str) -> int | None:
    match = WHATSAPP_FILENAME_RE.match(filename)
    if match is None:
        return None
    return int(match.group(3))


def is_whatsapp_media_filename(filename: str) -> bool:
    return WHATSAPP_FILENAME_RE.match(filename) is not None


def date_key_from_ms(timestamp_ms: int) -> str:
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    return dt.strftime("%Y-%m-%d")


def match_audio_files_to_messages(
    files: list[ZipAudioInput],
    messages: list[AudioMatchCandidate],
    *,
    tolerance_seconds: int = BATCH_MATCH_TOLERANCE_SECONDS,
) -> dict[str, AudioMatchResult]:
    matches: dict[str, AudioMatchResult] = {}
    used_files: set[str] = set()
    used_messages: set[UUID] = set()
    messages_by_day = _group_messages_by_day(messages)

    for file_key, result in _match_by_whatsapp_filename_index(
        files, messages_by_day, used_files, used_messages
    ).items():
        matches[file_key] = result

    for file_key, result in _match_by_timestamp(
        files,
        messages,
        used_files,
        used_messages,
        tolerance_seconds,
    ).items():
        matches[file_key] = result

    return matches


def _group_messages_by_day(
    messages: list[AudioMatchCandidate],
) -> dict[str, list[AudioMatchCandidate]]:
    grouped: dict[str, list[AudioMatchCandidate]] = {}
    for message in messages:
        day = date_key_from_ms(message.timestamp_ms)
        grouped.setdefault(day, []).append(message)
    for bucket in grouped.values():
        bucket.sort(key=lambda item: item.timestamp_ms)
    return grouped


def _match_by_whatsapp_filename_index(
    files: list[ZipAudioInput],
    messages_by_day: dict[str, list[AudioMatchCandidate]],
    used_files: set[str],
    used_messages: set[UUID],
) -> dict[str, AudioMatchResult]:
    matches: dict[str, AudioMatchResult] = {}
    for item in files:
        if item.file_key in used_files or not is_whatsapp_media_filename(item.filename):
            continue
        day = parse_whatsapp_filename_date(item.filename)
        sequence = parse_whatsapp_filename_sequence(item.filename)
        if day is None or sequence is None:
            continue
        day_messages = messages_by_day.get(day, [])
        if sequence >= len(day_messages):
            continue
        message = day_messages[sequence]
        if message.message_id in used_messages:
            continue
        used_files.add(item.file_key)
        used_messages.add(message.message_id)
        matches[item.file_key] = AudioMatchResult(
            message_id=message.message_id,
            diff_seconds=abs(item.modified_ms - message.timestamp_ms) / 1000,
            matched_by_filename_fallback=True,
        )
    return matches


def _match_by_timestamp(
    files: list[ZipAudioInput],
    messages: list[AudioMatchCandidate],
    used_files: set[str],
    used_messages: set[UUID],
    tolerance_seconds: int,
) -> dict[str, AudioMatchResult]:
    matches: dict[str, AudioMatchResult] = {}
    available_messages = [item for item in messages if item.message_id not in used_messages]
    remaining_files = [item for item in files if item.file_key not in used_files]

    pairs: list[tuple[str, UUID, float]] = []
    for file_item in remaining_files:
        for message in available_messages:
            diff = abs(file_item.modified_ms - message.timestamp_ms) / 1000
            pairs.append((file_item.file_key, message.message_id, diff))

    pairs.sort(key=lambda item: item[2])

    for file_key, message_id, diff_seconds in pairs:
        if diff_seconds > tolerance_seconds:
            continue
        if file_key in used_files or message_id in used_messages:
            continue
        used_files.add(file_key)
        used_messages.add(message_id)
        matches[file_key] = AudioMatchResult(
            message_id=message_id,
            diff_seconds=diff_seconds,
            matched_by_filename_fallback=False,
        )
    return matches

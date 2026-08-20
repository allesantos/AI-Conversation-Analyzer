"""Extrai exportações .zip do WhatsApp (chat .txt + mídias)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime

from app.conversation.media import is_audio_filename
from app.core.exceptions import BadRequestError

CHAT_TXT_PRIORITY = (
    "_chat.txt",
    "chat.txt",
)


@dataclass(frozen=True, slots=True)
class ZipAudioEntry:
    archive_path: str
    filename: str
    data: bytes
    modified_ms: int


@dataclass(frozen=True, slots=True)
class WhatsAppArchive:
    chat_filename: str
    chat_text: str
    audio_files: tuple[ZipAudioEntry, ...]


def extract_whatsapp_archive(
    payload: bytes,
    *,
    max_uncompressed_bytes: int,
    max_files: int,
) -> WhatsAppArchive:
    if not payload:
        raise BadRequestError("Arquivo .zip vazio.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise BadRequestError("Arquivo .zip inválido.") from exc

    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > max_files:
            raise BadRequestError("O .zip contém arquivos demais.")

        total_uncompressed = sum(info.file_size for info in infos)
        if total_uncompressed > max_uncompressed_bytes:
            raise BadRequestError("Conteúdo descompactado do .zip excede o limite permitido.")

        chat_info = _select_chat_txt(infos)
        if chat_info is None:
            raise BadRequestError("Nenhum arquivo .txt de conversa encontrado no .zip.")

        chat_bytes = archive.read(chat_info.filename)
        try:
            chat_text = chat_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BadRequestError("O chat .txt dentro do .zip não está em UTF-8.") from exc

        audio_files: list[ZipAudioEntry] = []
        for info in infos:
            basename = _basename(info.filename)
            if not is_audio_filename(basename):
                continue
            data = archive.read(info.filename)
            if not data:
                continue
            audio_files.append(
                ZipAudioEntry(
                    archive_path=info.filename,
                    filename=basename,
                    data=data,
                    modified_ms=_zip_modified_ms(info),
                )
            )

        return WhatsAppArchive(
            chat_filename=_basename(chat_info.filename),
            chat_text=chat_text,
            audio_files=tuple(audio_files),
        )


def _select_chat_txt(infos: list[zipfile.ZipInfo]) -> zipfile.ZipInfo | None:
    txt_infos = [info for info in infos if info.filename.lower().endswith(".txt")]
    if not txt_infos:
        return None

    lowered = {info.filename.lower(): info for info in txt_infos}
    for preferred in CHAT_TXT_PRIORITY:
        for path, info in lowered.items():
            if path.endswith(preferred):
                return info

    if len(txt_infos) == 1:
        return txt_infos[0]

    whatsapp_named = [
        info
        for info in txt_infos
        if "whatsapp" in _basename(info.filename).lower()
    ]
    if len(whatsapp_named) == 1:
        return whatsapp_named[0]

    return txt_infos[0]


def _basename(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


def _zip_modified_ms(info: zipfile.ZipInfo) -> int:
    dt = datetime(*info.date_time, tzinfo=UTC)
    return int(dt.timestamp() * 1000)

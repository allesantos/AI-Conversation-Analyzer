from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.conversation.media import is_audio_filename
from app.core.config import Settings
from app.core.exceptions import BadRequestError, PayloadTooLargeError


class AudioStorageService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = Path(settings.audio_storage_path)

    async def save_upload(
        self,
        conversation_id: UUID,
        upload: UploadFile,
    ) -> tuple[str, str]:
        filename = (upload.filename or "").strip()
        if not filename or not is_audio_filename(filename):
            raise BadRequestError(
                "Envie um arquivo de áudio válido (.opus, .ogg, .mp3, .m4a, .wav, .aac, .amr)."
            )

        if upload.size is not None and upload.size > self._settings.max_upload_bytes:
            raise PayloadTooLargeError("Arquivo excede o tamanho máximo permitido")

        extension = Path(filename).suffix.lower()
        stored_name = f"{uuid4()}{extension}"
        destination_dir = self._root / str(conversation_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / stored_name

        total = 0
        chunk_size = 1024 * 1024
        with destination.open("wb") as handle:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > self._settings.max_upload_bytes:
                    handle.close()
                    destination.unlink(missing_ok=True)
                    raise PayloadTooLargeError("Arquivo excede o tamanho máximo permitido")
                handle.write(chunk)

        if total == 0:
            destination.unlink(missing_ok=True)
            raise BadRequestError("Arquivo de áudio vazio.")

        return str(destination), filename

    def save_bytes(
        self,
        conversation_id: UUID,
        filename: str,
        data: bytes,
    ) -> tuple[str, str]:
        if not filename or not is_audio_filename(filename):
            raise BadRequestError(
                "Envie um arquivo de áudio válido (.opus, .ogg, .mp3, .m4a, .wav, .aac, .amr)."
            )
        if len(data) > self._settings.max_upload_bytes:
            raise PayloadTooLargeError("Arquivo excede o tamanho máximo permitido")
        if not data:
            raise BadRequestError("Arquivo de áudio vazio.")

        extension = Path(filename).suffix.lower()
        stored_name = f"{uuid4()}{extension}"
        destination_dir = self._root / str(conversation_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / stored_name
        destination.write_bytes(data)
        return str(destination), filename

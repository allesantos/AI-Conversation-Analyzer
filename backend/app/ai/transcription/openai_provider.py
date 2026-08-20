from __future__ import annotations

from pathlib import Path

from openai import AsyncOpenAI

from app.ai.transcription.provider import TranscriptionResult, TranscriptionUsage
from app.ai.transcription.whisper_compat import whisper_upload_filename


class OpenAIWhisperProvider:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def transcribe_file(self, file_path: str, *, filename: str) -> TranscriptionResult:
        path = Path(file_path)
        upload_name = whisper_upload_filename(file_path=file_path, original_filename=filename)
        with path.open("rb") as handle:
            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=(upload_name, handle),
            )
        duration = getattr(response, "duration", None)
        return TranscriptionResult(
            text=response.text.strip(),
            usage=TranscriptionUsage(
                provider="openai",
                model=self._model,
                duration_seconds=float(duration) if duration is not None else None,
            ),
        )

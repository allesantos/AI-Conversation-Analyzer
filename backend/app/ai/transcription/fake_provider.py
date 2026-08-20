from __future__ import annotations

import hashlib
from pathlib import Path

from app.ai.transcription.provider import TranscriptionResult, TranscriptionUsage


class FakeTranscriptionProvider:
    """Transcrição determinística para testes — sem rede."""

    def __init__(self, *, model: str = "fake-whisper") -> None:
        self._model = model

    async def transcribe_file(self, file_path: str, *, filename: str) -> TranscriptionResult:
        digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()[:12]
        text = f"Transcrição fictícia do áudio {filename} ({digest})."
        return TranscriptionResult(
            text=text,
            usage=TranscriptionUsage(
                provider="fake",
                model=self._model,
                duration_seconds=12.5,
            ),
        )

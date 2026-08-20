from __future__ import annotations

from app.ai.transcription.fake_provider import FakeTranscriptionProvider
from app.ai.transcription.openai_provider import OpenAIWhisperProvider
from app.ai.transcription.provider import TranscriptionProvider
from app.core.config import Settings
from app.core.exceptions import BadRequestError


def build_transcription_provider(settings: Settings) -> TranscriptionProvider:
    provider = settings.transcription_provider.strip().lower()
    if provider == "fake":
        return FakeTranscriptionProvider(model=settings.transcription_model)
    if provider == "openai":
        if not settings.openai_api_key.strip():
            raise BadRequestError(
                "OPENAI_API_KEY não configurada. Adicione uma chave no .env para transcrever áudio."
            )
        return OpenAIWhisperProvider(
            api_key=settings.openai_api_key,
            model=settings.transcription_model,
        )
    raise BadRequestError(f"Provedor de transcrição não suportado: {provider}")

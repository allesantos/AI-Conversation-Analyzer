from __future__ import annotations

from uuid import UUID

from arq import create_pool

from app.core.redis_settings import redis_settings_from_url


class ArqTranscriptionJobEnqueuer:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def enqueue_generate_transcription(self, transcription_id: UUID) -> None:
        pool = await create_pool(redis_settings_from_url(self._redis_url))
        try:
            await pool.enqueue_job("generate_transcription", str(transcription_id))
        finally:
            await pool.close()


class InlineTranscriptionJobEnqueuer:
    """Executa transcrição inline — usado em testes."""

    def __init__(self, runner) -> None:
        self._runner = runner

    async def enqueue_generate_transcription(self, transcription_id: UUID) -> None:
        await self._runner(transcription_id)

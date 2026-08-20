from uuid import UUID

from app.ai.embeddings.factory import build_embedding_provider
from app.ai.rag.pgvector_store import PgVectorStore
from app.ai.transcription.factory import build_transcription_provider
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.audio_storage import AudioStorageService
from app.services.embedding import EmbeddingGenerationService
from app.services.embedding_enqueue import ArqEmbeddingJobEnqueuer
from app.services.transcription import TranscriptionService
from app.services.transcription_enqueue import ArqTranscriptionJobEnqueuer


async def ping(ctx: dict) -> str:
    """Job de sanidade da fila."""
    _ = ctx
    _ = get_settings()
    return "pong"


async def generate_transcription(ctx: dict, transcription_id: str) -> str:
    """Transcreve áudio enviado pelo usuário."""
    _ = ctx
    settings = get_settings()
    async with SessionLocal() as session:
        service = TranscriptionService(
            session,
            settings,
            build_transcription_provider(settings),
            AudioStorageService(settings),
            ArqTranscriptionJobEnqueuer(settings.redis_url),
        )
        await service.process_transcription(UUID(transcription_id))
    return "ok"


async def generate_embeddings(ctx: dict, conversation_id: str) -> str:
    """Gera embeddings de chunks para conversas grandes (>10k mensagens)."""
    _ = ctx
    settings = get_settings()
    async with SessionLocal() as session:
        service = EmbeddingGenerationService(
            session,
            settings,
            build_embedding_provider(settings),
            PgVectorStore(session),
            ArqEmbeddingJobEnqueuer(settings.redis_url),
        )
        await service.generate_for_conversation(UUID(conversation_id))
    return "ok"

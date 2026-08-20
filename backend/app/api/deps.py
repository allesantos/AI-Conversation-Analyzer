from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.factory import build_embedding_provider
from app.ai.embeddings.provider import EmbeddingProvider
from app.ai.llm.factory import build_llm_provider
from app.ai.llm.provider import LLMProvider
from app.ai.rag.pgvector_store import PgVectorStore
from app.ai.rag.vector_store import VectorStore
from app.ai.transcription.factory import build_transcription_provider
from app.ai.transcription.provider import TranscriptionProvider
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.audio_storage import AudioStorageService
from app.services.embedding import EmbeddingGenerationService
from app.services.embedding_enqueue import ArqEmbeddingJobEnqueuer
from app.services.analysis import AnalysisService
from app.services.transcription import TranscriptionService
from app.services.transcription_enqueue import ArqTranscriptionJobEnqueuer

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    session: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Autenticação obrigatória")

    payload = decode_access_token(credentials.credentials, settings)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token inválido ou expirado")

    try:
        parsed_id = UUID(str(user_id))
    except ValueError as exc:
        raise UnauthorizedError("Token inválido ou expirado") from exc

    user = await UserRepository(session).get_by_id(parsed_id)
    if user is None:
        raise UnauthorizedError("Token inválido ou expirado")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_llm_provider(settings: AppSettings) -> LLMProvider:
    return build_llm_provider(settings)


def get_embedding_provider(settings: AppSettings) -> EmbeddingProvider:
    return build_embedding_provider(settings)


def get_vector_store(session: DbSession) -> VectorStore:
    return PgVectorStore(session)


def get_job_enqueuer(settings: AppSettings) -> ArqEmbeddingJobEnqueuer:
    return ArqEmbeddingJobEnqueuer(settings.redis_url)


def get_embedding_service(
    session: DbSession,
    settings: AppSettings,
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    job_enqueuer: Annotated[ArqEmbeddingJobEnqueuer, Depends(get_job_enqueuer)],
) -> EmbeddingGenerationService:
    return EmbeddingGenerationService(
        session,
        settings,
        embedding_provider,
        vector_store,
        job_enqueuer,
    )


EmbeddingServiceDep = Annotated[EmbeddingGenerationService, Depends(get_embedding_service)]


def get_analysis_service(
    session: DbSession,
    settings: AppSettings,
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
    embedding_service: EmbeddingServiceDep,
) -> AnalysisService:
    return AnalysisService(session, settings, llm, embedding_service)


AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]


def get_transcription_provider(settings: AppSettings) -> TranscriptionProvider:
    return build_transcription_provider(settings)


def get_audio_storage(settings: AppSettings) -> AudioStorageService:
    return AudioStorageService(settings)


def get_transcription_job_enqueuer(settings: AppSettings) -> ArqTranscriptionJobEnqueuer:
    return ArqTranscriptionJobEnqueuer(settings.redis_url)


def get_transcription_service(
    session: DbSession,
    settings: AppSettings,
    provider: Annotated[TranscriptionProvider, Depends(get_transcription_provider)],
    storage: Annotated[AudioStorageService, Depends(get_audio_storage)],
    job_enqueuer: Annotated[ArqTranscriptionJobEnqueuer, Depends(get_transcription_job_enqueuer)],
    embedding_service: EmbeddingServiceDep,
    analysis_service: AnalysisServiceDep,
) -> TranscriptionService:
    return TranscriptionService(
        session,
        settings,
        provider,
        storage,
        job_enqueuer,
        embedding_service,
        analysis_service,
    )


LLMDep = Annotated[LLMProvider, Depends(get_llm_provider)]
TranscriptionDep = Annotated[TranscriptionProvider, Depends(get_transcription_provider)]
TranscriptionServiceDep = Annotated[TranscriptionService, Depends(get_transcription_service)]
EmbeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]

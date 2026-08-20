from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.deps import (
    AppSettings,
    CurrentUser,
    DbSession,
    EmbeddingServiceDep,
    LLMDep,
    TranscriptionServiceDep,
    get_analysis_service,
)
from app.core.rate_limit import ai_rate_limiter
from app.response_engine.engine import ResponseEngine
from app.schemas.analysis import (
    AnalysisRead,
    AnalyzeResponse,
    AskRequest,
    AskResponse,
    ProcessingStatusResponse,
    TimelineRead,
)
from app.schemas.audio import AudioTranscriptionRead, AudioTranscriptionStartedResponse
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationList,
    ConversationRead,
    ImportSummary,
    ManualTranscriptionCreate,
    MessageRead,
    ParticipantRead,
    SetOwnerRequest,
)
from app.schemas.suggestion import SuggestionsRequest, SuggestionsResponse
from app.services.analysis import AnalysisService
from app.services.conversation import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(
    session: DbSession,
    embedding_service: EmbeddingServiceDep,
    transcription_service: TranscriptionServiceDep,
) -> ConversationService:
    return ConversationService(session, embedding_service, transcription_service)


def get_response_engine(
    session: DbSession,
    settings: AppSettings,
    llm: LLMDep,
    embedding_service: EmbeddingServiceDep,
) -> ResponseEngine:
    return ResponseEngine(session, settings, llm, embedding_service)


ConversationSvc = Annotated[ConversationService, Depends(get_conversation_service)]
AnalysisSvc = Annotated[AnalysisService, Depends(get_analysis_service)]
ResponseEngineSvc = Annotated[ResponseEngine, Depends(get_response_engine)]
TranscriptionSvc = TranscriptionServiceDep


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    current_user: CurrentUser,
    service: ConversationSvc,
) -> ConversationRead:
    return await service.create(current_user.id, payload)


@router.get("", response_model=ConversationList)
async def list_conversations(
    current_user: CurrentUser,
    service: ConversationSvc,
) -> ConversationList:
    return await service.list_for_user(current_user.id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: ConversationSvc,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ConversationDetail:
    return await service.get_detail(
        conversation_id,
        current_user.id,
        offset=offset,
        limit=limit,
    )


@router.get("/{conversation_id}/messages/analysis-only", response_model=list[MessageRead])
async def list_analysis_only_messages(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: ConversationSvc,
) -> list[MessageRead]:
    return await service.list_analysis_only_messages(conversation_id, current_user.id)


@router.get("/{conversation_id}/messages/{message_id}", response_model=MessageRead)
async def get_conversation_message(
    conversation_id: UUID,
    message_id: UUID,
    current_user: CurrentUser,
    service: ConversationSvc,
) -> MessageRead:
    return await service.get_message(conversation_id, message_id, current_user.id)


@router.delete("/{conversation_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis_message(
    conversation_id: UUID,
    message_id: UUID,
    current_user: CurrentUser,
    service: TranscriptionSvc,
) -> Response:
    await service.delete_analysis_message(conversation_id, message_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/import", response_model=ImportSummary)
async def import_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: ConversationSvc,
    analysis_service: AnalysisSvc,
    file: Annotated[UploadFile, File()],
    owner_name: Annotated[str | None, Form()] = None,
) -> ImportSummary:
    summary = await service.import_whatsapp_file(
        conversation_id,
        current_user.id,
        file,
        owner_name,
    )
    await analysis_service.reconcile_after_import(conversation_id, current_user.id)
    return summary


@router.post("/{conversation_id}/owner", response_model=list[ParticipantRead])
async def set_conversation_owner(
    conversation_id: UUID,
    payload: SetOwnerRequest,
    current_user: CurrentUser,
    service: ConversationSvc,
) -> list[ParticipantRead]:
    return await service.set_owner(
        conversation_id,
        current_user.id,
        payload.participant_id,
    )


@router.post(
    "/{conversation_id}/analyze",
    response_model=AnalyzeResponse,
    responses={202: {"model": ProcessingStatusResponse}},
)
async def analyze_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: AnalysisSvc,
    force: Annotated[bool, Query(description="Ignora cache e regenera o resumo via LLM")] = False,
) -> AnalyzeResponse:
    ai_rate_limiter.check(current_user.id)
    return await service.analyze(conversation_id, current_user.id, force=force)


@router.get("/{conversation_id}/analysis", response_model=AnalyzeResponse)
async def get_conversation_analysis(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: AnalysisSvc,
) -> AnalyzeResponse:
    return await service.get_analysis(conversation_id, current_user.id)


@router.get("/{conversation_id}/timeline", response_model=TimelineRead)
async def get_conversation_timeline(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: AnalysisSvc,
) -> TimelineRead:
    return await service.get_timeline(conversation_id, current_user.id)


@router.post(
    "/{conversation_id}/ask",
    response_model=AskResponse,
    responses={202: {"model": ProcessingStatusResponse}},
)
async def ask_conversation(
    conversation_id: UUID,
    payload: AskRequest,
    current_user: CurrentUser,
    service: AnalysisSvc,
) -> AskResponse:
    ai_rate_limiter.check(current_user.id)
    return await service.ask(conversation_id, current_user.id, payload.question)


@router.post(
    "/{conversation_id}/suggestions",
    response_model=SuggestionsResponse,
)
async def generate_suggestions(
    conversation_id: UUID,
    payload: SuggestionsRequest,
    current_user: CurrentUser,
    engine: ResponseEngineSvc,
) -> SuggestionsResponse:
    ai_rate_limiter.check(current_user.id)
    return await engine.generate(
        conversation_id,
        current_user.id,
        incoming_message=payload.incoming_message,
    )


@router.post(
    "/{conversation_id}/manual-transcription",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_transcription(
    conversation_id: UUID,
    payload: ManualTranscriptionCreate,
    current_user: CurrentUser,
    service: TranscriptionSvc,
) -> MessageRead:
    return await service.create_manual_transcription(
        conversation_id,
        current_user.id,
        text=payload.text,
        message_id=payload.message_id,
    )


@router.post(
    "/{conversation_id}/audio",
    response_model=AudioTranscriptionStartedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_audio(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: TranscriptionSvc,
    file: Annotated[UploadFile, File()],
    message_id: Annotated[UUID | None, Form()] = None,
    sender_id: Annotated[UUID | None, Form()] = None,
    timestamp: Annotated[datetime | None, Form()] = None,
) -> AudioTranscriptionStartedResponse:
    return await service.start_upload(
        conversation_id,
        current_user.id,
        file,
        message_id=message_id,
        sender_id=sender_id,
        timestamp=timestamp,
    )


@router.get(
    "/{conversation_id}/audio/{transcription_id}",
    response_model=AudioTranscriptionRead,
)
async def get_audio_transcription(
    conversation_id: UUID,
    transcription_id: UUID,
    current_user: CurrentUser,
    service: TranscriptionSvc,
) -> AudioTranscriptionRead:
    return await service.get_transcription(conversation_id, transcription_id, current_user.id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: ConversationSvc,
) -> Response:
    await service.delete_for_user(conversation_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.transcription.provider import TranscriptionProvider
from app.conversation.types import MessageType
from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.audio_transcription import AudioTranscription, TranscriptionStatus
from app.models.message import Message
from app.repositories.analysis import ConversationAnalysisRepository
from app.repositories.audio_transcription import AudioTranscriptionRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository, ParticipantRepository
from app.schemas.audio import AudioTranscriptionRead, AudioTranscriptionStartedResponse
from app.schemas.conversation import MessageRead
from app.services.audio_storage import AudioStorageService
from app.services.embedding import EmbeddingGenerationService
from app.services.transcription_enqueue import (
    ArqTranscriptionJobEnqueuer,
    InlineTranscriptionJobEnqueuer,
)
from app.services.usage import record_transcription_usage

if False:  # pragma: no cover - typing only
    from app.services.analysis import AnalysisService


class TranscriptionService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: TranscriptionProvider,
        storage: AudioStorageService,
        job_enqueuer: ArqTranscriptionJobEnqueuer | InlineTranscriptionJobEnqueuer,
        embedding_service: EmbeddingGenerationService | None = None,
        analysis_service: "AnalysisService | None" = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider
        self.storage = storage
        self.job_enqueuer = job_enqueuer
        self.embedding_service = embedding_service
        self.analysis_service = analysis_service
        self.conversations = ConversationRepository(session)
        self.participants = ParticipantRepository(session)
        self.messages = MessageRepository(session)
        self.transcriptions = AudioTranscriptionRepository(session)
        self.analyses = ConversationAnalysisRepository(session)

    async def start_upload(
        self,
        conversation_id: UUID,
        user_id: UUID,
        upload: UploadFile,
        *,
        message_id: UUID | None,
        sender_id: UUID | None,
        timestamp: datetime | None,
    ) -> AudioTranscriptionStartedResponse:
        await self._owned(conversation_id, user_id)
        data = await upload.read()
        filename = upload.filename or "audio"
        file_hash = hashlib.sha256(data).hexdigest()

        # Áudio solto (sem message_id): se o hash já existe, não cria mensagem duplicada.
        if message_id is None:
            by_hash = await self.transcriptions.get_completed_by_file_hash(
                conversation_id,
                file_hash,
            )
            if by_hash is not None and by_hash.transcribed_text:
                return AudioTranscriptionStartedResponse(
                    transcription_id=by_hash.id,
                    message_id=by_hash.message_id,
                    status=TranscriptionStatus.COMPLETED,
                    message="Áudio já transcrito — Whisper não chamado.",
                    reused=True,
                )

        message = await self._resolve_message(
            conversation_id,
            message_id=message_id,
            sender_id=sender_id,
            timestamp=timestamp,
        )
        return await self._start_transcription_from_bytes(
            conversation_id,
            message=message,
            filename=filename,
            data=data,
            file_hash=file_hash,
        )

    async def start_upload_bytes(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        message_id: UUID,
        filename: str,
        data: bytes,
    ) -> AudioTranscriptionStartedResponse:
        await self._owned(conversation_id, user_id)
        message = await self.messages.get_by_id(conversation_id, message_id)
        if message is None:
            raise NotFoundError("Mensagem não encontrada nesta conversa")
        return await self._start_transcription_from_bytes(
            conversation_id,
            message=message,
            filename=filename,
            data=data,
        )

    async def _start_transcription_from_bytes(
        self,
        conversation_id: UUID,
        *,
        message: Message,
        filename: str,
        data: bytes,
        file_hash: str | None = None,
    ) -> AudioTranscriptionStartedResponse:
        resolved_hash = file_hash or hashlib.sha256(data).hexdigest()

        existing = await self.transcriptions.get_latest_for_message(message.id)
        if existing is not None:
            if existing.status == TranscriptionStatus.COMPLETED and existing.transcribed_text:
                if not existing.file_hash:
                    existing.file_hash = resolved_hash
                    await self.transcriptions.save(existing)
                    await self.session.commit()
                return AudioTranscriptionStartedResponse(
                    transcription_id=existing.id,
                    message_id=message.id,
                    status=TranscriptionStatus.COMPLETED,
                    message="Áudio já transcrito — Whisper não chamado.",
                    reused=True,
                )
            if existing.status in {
                TranscriptionStatus.PENDING,
                TranscriptionStatus.PROCESSING,
            }:
                return AudioTranscriptionStartedResponse(
                    transcription_id=existing.id,
                    message_id=message.id,
                    status=existing.status,
                    message="Transcrição já em andamento para esta mensagem.",
                    reused=True,
                )

        by_hash = await self.transcriptions.get_completed_by_file_hash(
            conversation_id,
            resolved_hash,
        )
        if by_hash is not None and by_hash.transcribed_text:
            return await self._reuse_completed_transcription(
                message=message,
                source=by_hash,
                filename=filename,
                file_hash=resolved_hash,
            )

        file_path, original_filename = self.storage.save_bytes(
            conversation_id,
            filename,
            data,
        )

        transcription = AudioTranscription(
            conversation_id=conversation_id,
            message_id=message.id,
            file_path=file_path,
            file_hash=resolved_hash,
            status=TranscriptionStatus.PENDING,
        )
        transcription = await self.transcriptions.add(transcription)

        metadata = dict(message.message_metadata or {})
        metadata.update(
            {
                "attachment": True,
                "filename": original_filename,
                "transcription_id": str(transcription.id),
                "transcription_status": TranscriptionStatus.PENDING,
                "file_hash": resolved_hash,
            }
        )
        await self.messages.update_content(message, content=message.content, metadata=metadata)
        await self.session.commit()

        await self.job_enqueuer.enqueue_generate_transcription(transcription.id)

        return AudioTranscriptionStartedResponse(
            transcription_id=transcription.id,
            message_id=message.id,
            status=TranscriptionStatus.PENDING,
            message="Transcrição enfileirada. Consulte o status em alguns instantes.",
            reused=False,
        )

    async def _reuse_completed_transcription(
        self,
        *,
        message: Message,
        source: AudioTranscription,
        filename: str,
        file_hash: str,
    ) -> AudioTranscriptionStartedResponse:
        transcription = AudioTranscription(
            conversation_id=message.conversation_id,
            message_id=message.id,
            file_path=source.file_path,
            file_hash=file_hash,
            transcribed_text=source.transcribed_text,
            transcription_provider=source.transcription_provider,
            transcription_model=source.transcription_model,
            duration_seconds=source.duration_seconds,
            status=TranscriptionStatus.COMPLETED,
        )
        transcription = await self.transcriptions.add(transcription)

        metadata = dict(message.message_metadata or {})
        metadata.update(
            {
                "attachment": True,
                "filename": filename,
                "transcribed": True,
                "transcription_id": str(transcription.id),
                "transcription_status": TranscriptionStatus.COMPLETED,
                "transcription_provider": source.transcription_provider,
                "transcription_model": source.transcription_model,
                "file_hash": file_hash,
                "transcription_reused": True,
            }
        )
        if source.duration_seconds is not None:
            metadata["duration_seconds"] = source.duration_seconds

        await self.messages.update_content(
            message,
            content=source.transcribed_text or message.content,
            metadata=metadata,
            message_type=MessageType.AUDIO.value
            if message.type != MessageType.AUDIO.value
            else None,
        )
        await self.session.commit()

        return AudioTranscriptionStartedResponse(
            transcription_id=transcription.id,
            message_id=message.id,
            status=TranscriptionStatus.COMPLETED,
            message="Transcrição reutilizada (mesmo arquivo) — Whisper não chamado.",
            reused=True,
        )

    async def get_transcription(
        self,
        conversation_id: UUID,
        transcription_id: UUID,
        user_id: UUID,
    ) -> AudioTranscriptionRead:
        await self._owned(conversation_id, user_id)
        row = await self.transcriptions.get_for_conversation(transcription_id, conversation_id)
        if row is None:
            raise NotFoundError("Transcrição não encontrada")
        return AudioTranscriptionRead.model_validate(row)

    async def create_manual_transcription(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        text: str,
        message_id: UUID,
    ) -> MessageRead:
        await self._owned(conversation_id, user_id)
        content = text.strip()
        if not content:
            raise BadRequestError("Informe o texto da transcrição.")

        message = await self.messages.get_by_id(conversation_id, message_id)
        if message is None:
            raise NotFoundError("Mensagem não encontrada nesta conversa")
        if message.type not in {
            MessageType.AUDIO.value,
            MessageType.MEDIA_OCULTA.value,
        }:
            raise BadRequestError(
                "Só é possível colar texto em mensagens de áudio ou mídia oculta."
            )

        metadata = dict(message.message_metadata or {})
        metadata.update(
            {
                "transcribed": True,
                "manual_transcription": True,
                "source": "manual",
                "source_format": "plain",
                "transcription_status": TranscriptionStatus.COMPLETED,
                "transcription_provider": "manual",
                "transcription_model": "manual",
            }
        )
        message = await self.messages.update_content(
            message,
            content=content,
            metadata=metadata,
            message_type=MessageType.AUDIO.value
            if message.type != MessageType.AUDIO.value
            else None,
        )

        await self._refresh_analysis_after_data_change(conversation_id, user_id=user_id)
        await self.session.commit()

        participants = await self.participants.list_for_conversation(conversation_id)
        names = {item.id: item.name for item in participants}
        return MessageRead(
            id=message.id,
            sender_id=message.sender_id,
            sender_name=names.get(message.sender_id) if message.sender_id else None,
            timestamp=message.timestamp,
            type=message.type,  # type: ignore[arg-type]
            content=message.content,
            metadata=message.message_metadata or {},
        )

    async def delete_analysis_message(
        self,
        conversation_id: UUID,
        message_id: UUID,
        user_id: UUID,
    ) -> None:
        await self._owned(conversation_id, user_id)
        message = await self.messages.get_by_id(conversation_id, message_id)
        if message is None:
            raise NotFoundError("Mensagem não encontrada nesta conversa")

        metadata = message.message_metadata or {}
        if metadata.get("analysis_only") is not True:
            raise BadRequestError(
                "Somente áudios importados fora da timeline podem ser excluídos desta forma."
            )

        transcription = await self.transcriptions.get_latest_for_message(message_id)
        if transcription is not None and transcription.file_path:
            Path(transcription.file_path).unlink(missing_ok=True)

        deleted = await self.messages.delete_by_id(conversation_id, message_id)
        if not deleted:
            raise NotFoundError("Mensagem não encontrada nesta conversa")

        await self._refresh_analysis_after_data_change(conversation_id, user_id=user_id)
        await self.session.commit()

    async def process_transcription(self, transcription_id: UUID) -> None:
        row = await self.transcriptions.get_by_id(transcription_id)
        if row is None:
            return

        row.status = TranscriptionStatus.PROCESSING
        await self.transcriptions.save(row)
        await self.session.commit()

        message = await self.messages.get_by_id(row.conversation_id, row.message_id)
        if message is None:
            row.status = TranscriptionStatus.FAILED
            row.error_message = "Mensagem associada não encontrada."
            await self.transcriptions.save(row)
            await self.session.commit()
            return

        try:
            result = await self.provider.transcribe_file(
                row.file_path,
                filename=_filename_from_metadata(message.message_metadata),
            )
            metadata = dict(message.message_metadata or {})
            metadata.update(
                {
                    "transcribed": True,
                    "transcription_id": str(row.id),
                    "transcription_status": TranscriptionStatus.COMPLETED,
                    "transcription_provider": result.usage.provider,
                    "transcription_model": result.usage.model,
                }
            )
            if result.usage.duration_seconds is not None:
                metadata["duration_seconds"] = result.usage.duration_seconds

            await self.messages.update_content(
                message,
                content=result.text,
                metadata=metadata,
                message_type=MessageType.AUDIO.value
                if message.type != MessageType.AUDIO.value
                else None,
            )

            row.transcribed_text = result.text
            row.transcription_provider = result.usage.provider
            row.transcription_model = result.usage.model
            row.duration_seconds = result.usage.duration_seconds
            row.status = TranscriptionStatus.COMPLETED
            row.error_message = None
            if not row.file_hash and row.file_path:
                try:
                    row.file_hash = hashlib.sha256(Path(row.file_path).read_bytes()).hexdigest()
                except OSError:
                    pass
            await self.transcriptions.save(row)

            conv = await self.conversations.get_by_id(row.conversation_id)
            if conv:
                await record_transcription_usage(
                    self.session,
                    user_id=conv.user_id,
                    conversation_id=row.conversation_id,
                    operation="transcription",
                    usage=result.usage,
                )

            await self._refresh_analysis_after_data_change(row.conversation_id)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            failed = await self.transcriptions.get_by_id(transcription_id)
            if failed is None:
                return
            failed.status = TranscriptionStatus.FAILED
            failed.error_message = str(exc)
            await self.transcriptions.save(failed)
            msg = await self.messages.get_by_id(row.conversation_id, row.message_id)
            if msg is not None:
                metadata = dict(msg.message_metadata or {})
                metadata["transcription_status"] = TranscriptionStatus.FAILED
                await self.messages.update_content(msg, content=msg.content, metadata=metadata)
            await self.session.commit()
            raise

    async def _resolve_message(
        self,
        conversation_id: UUID,
        *,
        message_id: UUID | None,
        sender_id: UUID | None,
        timestamp: datetime | None,
    ) -> Message:
        if message_id is not None:
            message = await self.messages.get_by_id(conversation_id, message_id)
            if message is None:
                raise NotFoundError("Mensagem não encontrada nesta conversa")
            return message

        if sender_id is None or timestamp is None:
            raise BadRequestError(
                "Informe message_id ou sender_id e timestamp para criar uma nova mensagem."
            )

        participants = await self.participants.list_for_conversation(conversation_id)
        if sender_id not in {item.id for item in participants}:
            raise BadRequestError("Participante inválido para esta conversa")

        normalized_ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            timestamp=normalized_ts,
            type="AUDIO",
            content="Áudio enviado pelo usuário",
            message_metadata={
                "attachment": True,
                "uploaded": True,
                "analysis_only": True,
            },
        )
        return await self.messages.add(message)

    async def _refresh_analysis_after_data_change(
        self,
        conversation_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> None:
        if self.analysis_service is None:
            return

        resolved_user_id = user_id
        if resolved_user_id is None:
            conv = await self.conversations.get_by_id(conversation_id)
            resolved_user_id = conv.user_id if conv else None

        if resolved_user_id is None:
            return

        refreshed = await self.analysis_service.refresh_derived_analysis(
            conversation_id,
            resolved_user_id,
        )
        if refreshed is not None:
            return

        await self._invalidate_derived_data(conversation_id)

    async def _invalidate_derived_data(self, conversation_id: UUID) -> None:
        await self.analyses.delete_for_conversation(conversation_id)
        if self.embedding_service is not None:
            await self.embedding_service.invalidate_for_conversation(conversation_id)
            return
        from app.ai.rag.pgvector_store import PgVectorStore
        from app.repositories.embedding import EmbeddingJobRepository, EmbeddingUsageRepository

        await PgVectorStore(self.session).delete_for_conversation(conversation_id)
        await EmbeddingJobRepository(self.session).delete_for_conversation(conversation_id)
        await EmbeddingUsageRepository(self.session).delete_for_conversation(conversation_id)

    async def _owned(self, conversation_id: UUID, user_id: UUID) -> None:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada")


def _filename_from_metadata(metadata: dict[str, object] | None) -> str:
    if not metadata:
        return "audio"
    filename = metadata.get("filename")
    return str(filename) if filename else "audio"

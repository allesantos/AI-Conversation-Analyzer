from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.audio_batch_match import (
    AudioMatchCandidate,
    ZipAudioInput,
    match_audio_files_to_messages,
)
from app.conversation.message_identity import (
    attachment_identity_key,
    is_attachment_message,
    message_identity_key,
)
from app.conversation.normalizer import ConversationNormalizer
from app.conversation.streaming import iter_limited_text_lines
from app.conversation.types import MessageType, ParticipantRole
from app.conversation.whatsapp_parser import WhatsAppParser
from app.conversation.whatsapp_zip import extract_whatsapp_archive
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, NotFoundError, PayloadTooLargeError
from app.models.conversation import Conversation
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository, ParticipantRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationList,
    ConversationRead,
    ImportSummary,
    MessageRead,
    ParticipantRead,
)
from app.services.embedding import EmbeddingGenerationService

if False:  # pragma: no cover - typing only
    from app.services.transcription import TranscriptionService


class ConversationService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingGenerationService | None = None,
        transcription_service: "TranscriptionService | None" = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service
        self.transcription_service = transcription_service
        self.conversations = ConversationRepository(session)
        self.participants = ParticipantRepository(session)
        self.messages = MessageRepository(session)

    async def create(self, user_id: UUID, payload: ConversationCreate) -> ConversationRead:
        conversation = Conversation(user_id=user_id, title=payload.title.strip())
        conversation = await self.conversations.add(conversation)
        await self.session.commit()
        return ConversationRead.model_validate(conversation)

    async def list_for_user(self, user_id: UUID) -> ConversationList:
        items = await self.conversations.list_for_user(user_id)
        total = await self.conversations.count_for_user(user_id)
        return ConversationList(
            items=[ConversationRead.model_validate(item) for item in items],
            total=total,
        )

    async def get_detail(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> ConversationDetail:
        conversation = await self._owned(conversation_id, user_id)
        participants = await self.participants.list_for_conversation(conversation.id)
        messages = await self.messages.list_page(conversation.id, offset=offset, limit=limit)
        total_messages = await self.messages.count_for_conversation(conversation.id)
        names = {item.id: item.name for item in participants}
        return ConversationDetail(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            participants=[ParticipantRead.model_validate(item) for item in participants],
            messages=[
                MessageRead(
                    id=message.id,
                    sender_id=message.sender_id,
                    sender_name=names.get(message.sender_id) if message.sender_id else None,
                    timestamp=message.timestamp,
                    type=message.type,  # type: ignore[arg-type]
                    content=message.content,
                    metadata=message.message_metadata or {},
                )
                for message in messages
            ],
            total_messages=total_messages,
            offset=offset,
            limit=limit,
        )

    async def get_message(
        self,
        conversation_id: UUID,
        message_id: UUID,
        user_id: UUID,
    ) -> MessageRead:
        conversation = await self._owned(conversation_id, user_id)
        message = await self.messages.get_by_id(conversation.id, message_id)
        if message is None:
            raise NotFoundError("Mensagem não encontrada nesta conversa")
        participants = await self.participants.list_for_conversation(conversation.id)
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

    async def list_analysis_only_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> list[MessageRead]:
        conversation = await self._owned(conversation_id, user_id)
        participants = await self.participants.list_for_conversation(conversation.id)
        names = {item.id: item.name for item in participants}
        rows = await self.messages.list_analysis_only(conversation.id)
        return [
            MessageRead(
                id=message.id,
                sender_id=message.sender_id,
                sender_name=names.get(message.sender_id) if message.sender_id else None,
                timestamp=message.timestamp,
                type=message.type,  # type: ignore[arg-type]
                content=message.content,
                metadata=message.message_metadata or {},
            )
            for message in rows
        ]

    async def delete_for_user(self, conversation_id: UUID, user_id: UUID) -> None:
        conversation = await self._owned(conversation_id, user_id)
        await self.conversations.delete(conversation)
        await self.session.commit()

    async def set_owner(
        self,
        conversation_id: UUID,
        user_id: UUID,
        participant_id: UUID,
    ) -> list[ParticipantRead]:
        conversation = await self._owned(conversation_id, user_id)
        participants = await self.participants.list_for_conversation(conversation.id)
        if not participants:
            raise BadRequestError("Importe a conversa antes de definir quem é você.")

        target = next((item for item in participants if item.id == participant_id), None)
        if target is None:
            raise NotFoundError("Participante não encontrado nesta conversa")

        for item in participants:
            item.role = (
                ParticipantRole.OWNER.value
                if item.id == participant_id
                else ParticipantRole.OTHER.value
            )
            await self.participants.save(item)

        conversation.updated_at = datetime.now(UTC)
        await self.session.commit()
        stored = await self.participants.list_for_conversation(conversation.id)
        return [ParticipantRead.model_validate(item) for item in stored]

    async def import_whatsapp_file(
        self,
        conversation_id: UUID,
        user_id: UUID,
        upload: UploadFile,
        owner_name: str | None,
    ) -> ImportSummary:
        filename = (upload.filename or "").lower()
        if filename.endswith(".zip"):
            return await self.import_whatsapp_zip(
                conversation_id,
                user_id,
                upload,
                owner_name,
            )
        if filename.endswith(".txt"):
            return await self.import_whatsapp_txt(
                conversation_id,
                user_id,
                upload,
                owner_name,
            )
        raise BadRequestError("Envie um arquivo .txt ou .zip exportado do WhatsApp")

    async def import_whatsapp_txt(
        self,
        conversation_id: UUID,
        user_id: UUID,
        upload: UploadFile,
        owner_name: str | None,
    ) -> ImportSummary:
        conversation = await self._owned(conversation_id, user_id)
        _validate_import_upload(upload)

        settings = get_settings()
        if upload.size is not None and upload.size > settings.max_upload_bytes:
            raise PayloadTooLargeError("Arquivo excede o tamanho máximo permitido")

        parser = WhatsAppParser()
        return await self._import_from_line_iterable(
            conversation,
            owner_name=owner_name,
            lines=iter_limited_text_lines(upload.file, settings.max_upload_bytes),
            parser=parser,
            import_format="txt",
        )

    async def import_whatsapp_zip(
        self,
        conversation_id: UUID,
        user_id: UUID,
        upload: UploadFile,
        owner_name: str | None,
    ) -> ImportSummary:
        conversation = await self._owned(conversation_id, user_id)
        _validate_import_upload(upload)

        settings = get_settings()
        payload = await upload.read()
        if len(payload) > settings.max_zip_upload_bytes:
            raise PayloadTooLargeError("Arquivo .zip excede o tamanho máximo permitido")

        archive = extract_whatsapp_archive(
            payload,
            max_uncompressed_bytes=settings.max_zip_uncompressed_bytes,
            max_files=settings.max_zip_files,
        )

        parser = WhatsAppParser()
        summary = await self._import_from_line_iterable(
            conversation,
            owner_name=owner_name,
            lines=archive.chat_text.splitlines(keepends=True),
            parser=parser,
            import_format="zip",
            audio_files_found=len(archive.audio_files),
        )

        if not archive.audio_files or self.transcription_service is None:
            return summary

        rows = await self.messages.list_all_for_conversation(conversation.id)
        candidates = [
            AudioMatchCandidate(
                message_id=row.id,
                timestamp_ms=int(row.timestamp.timestamp() * 1000),
            )
            for row in rows
            if row.type == MessageType.MEDIA_OCULTA.value
        ]
        audio_inputs = [
            ZipAudioInput(
                file_key=entry.archive_path,
                filename=entry.filename,
                modified_ms=entry.modified_ms,
            )
            for entry in archive.audio_files
        ]
        matches = match_audio_files_to_messages(audio_inputs, candidates)

        started = 0
        reused = 0
        for entry in archive.audio_files:
            match = matches.get(entry.archive_path)
            if match is None:
                continue
            result = await self.transcription_service.start_upload_bytes(
                conversation.id,
                user_id,
                message_id=match.message_id,
                filename=entry.filename,
                data=entry.data,
            )
            if result.reused:
                reused += 1
            else:
                started += 1

        return summary.model_copy(
            update={
                "audio_files_matched": len(matches),
                "audio_transcriptions_started": started,
                "audio_transcriptions_reused": reused,
            }
        )

    async def _import_from_line_iterable(
        self,
        conversation: Conversation,
        *,
        owner_name: str | None,
        lines,
        parser: WhatsAppParser,
        import_format: str,
        audio_files_found: int = 0,
    ) -> ImportSummary:
        normalizer = ConversationNormalizer(owner_name=owner_name)
        settings = get_settings()
        created_at = datetime.now(UTC)

        existing_participants = await self.participants.list_for_conversation(conversation.id)
        name_to_id: dict[str, UUID] = {p.name: p.id for p in existing_participants}

        existing_messages = await self.messages.list_all_for_conversation(conversation.id)
        id_to_name = {p.id: p.name for p in existing_participants}
        existing_keys: set[str] = set()
        for row in existing_messages:
            sender_name = id_to_name.get(row.sender_id) if row.sender_id else None
            meta = row.message_metadata if isinstance(row.message_metadata, dict) else None
            stored_key = meta.get("import_key") if meta else None
            if isinstance(stored_key, str) and stored_key:
                existing_keys.add(stored_key)
            else:
                existing_keys.add(
                    message_identity_key(
                        timestamp=row.timestamp,
                        message_type=row.type,
                        sender_name=sender_name,
                        content=row.content,
                    )
                )
            if is_attachment_message(message_type=row.type, metadata=meta):
                existing_keys.add(
                    attachment_identity_key(
                        timestamp=row.timestamp,
                        sender_name=sender_name,
                    )
                )

        pending_participants: list[dict[str, object]] = []
        pending_messages: list[dict[str, object]] = []
        total_messages = 0
        messages_added = 0
        messages_skipped = 0
        first_at: datetime | None = None
        last_at: datetime | None = None
        seen_in_file: set[str] = set()

        for parsed in parser.parse_lines(lines):
            normalized = normalizer.normalize_message(parsed)
            key = message_identity_key(
                timestamp=normalized.timestamp,
                message_type=normalized.message_type.value,
                sender_name=normalized.sender_name,
                content=normalized.content,
            )
            attachment_key = None
            if is_attachment_message(
                message_type=normalized.message_type.value,
                metadata=normalized.metadata,
            ):
                attachment_key = attachment_identity_key(
                    timestamp=normalized.timestamp,
                    sender_name=normalized.sender_name,
                )

            total_messages += 1
            if first_at is None or normalized.timestamp < first_at:
                first_at = normalized.timestamp
            if last_at is None or normalized.timestamp > last_at:
                last_at = normalized.timestamp

            duplicate = (
                key in existing_keys
                or key in seen_in_file
                or (attachment_key is not None and attachment_key in existing_keys)
                or (attachment_key is not None and attachment_key in seen_in_file)
            )
            if duplicate:
                messages_skipped += 1
                seen_in_file.add(key)
                if attachment_key is not None:
                    seen_in_file.add(attachment_key)
                continue
            seen_in_file.add(key)
            if attachment_key is not None:
                seen_in_file.add(attachment_key)

            sender_id = None
            if normalized.sender_name:
                sender_id = name_to_id.get(normalized.sender_name)
                if sender_id is None:
                    participant = normalizer.participants[normalized.sender_name]
                    sender_id = uuid4()
                    name_to_id[normalized.sender_name] = sender_id
                    pending_participants.append(
                        {
                            "id": sender_id,
                            "conversation_id": conversation.id,
                            "name": participant.name,
                            "role": participant.role.value,
                        }
                    )

            metadata = dict(normalized.metadata or {})
            metadata["import_key"] = key

            pending_messages.append(
                {
                    "id": uuid4(),
                    "conversation_id": conversation.id,
                    "sender_id": sender_id,
                    "timestamp": normalized.timestamp,
                    "type": normalized.message_type.value,
                    "content": normalized.content,
                    "message_metadata": metadata,
                    "created_at": created_at,
                }
            )
            messages_added += 1
            existing_keys.add(key)
            if attachment_key is not None:
                existing_keys.add(attachment_key)

            if len(pending_messages) >= settings.import_batch_size:
                await self.participants.bulk_insert(pending_participants)
                pending_participants.clear()
                await self.messages.bulk_insert(pending_messages)
                pending_messages.clear()

        await self.participants.bulk_insert(pending_participants)
        await self.messages.bulk_insert(pending_messages)

        if messages_added > 0:
            await self._invalidate_embeddings(conversation.id)

        await self._ensure_owner_role(conversation.id)

        conversation.updated_at = datetime.now(UTC)
        await self.session.commit()

        stored = await self.participants.list_for_conversation(conversation.id)
        return ImportSummary(
            conversation_id=conversation.id,
            total_messages=total_messages,
            skipped_lines=parser.skipped_line_count,
            participants=[ParticipantRead.model_validate(item) for item in stored],
            first_message_at=first_at,
            last_message_at=last_at,
            import_format=import_format,
            messages_added=messages_added,
            messages_skipped_duplicate=messages_skipped,
            audio_files_found=audio_files_found,
        )

    async def _ensure_owner_role(self, conversation_id: UUID) -> None:
        """Se só houver um participante, define OWNER automaticamente."""
        stored = await self.participants.list_for_conversation(conversation_id)
        if not stored:
            return
        if any(item.role == ParticipantRole.OWNER.value for item in stored):
            return
        if len(stored) == 1:
            stored[0].role = ParticipantRole.OWNER.value
            await self.participants.save(stored[0])

    async def _owned(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada")
        return conversation

    async def _invalidate_embeddings(self, conversation_id: UUID) -> None:
        if self.embedding_service is not None:
            await self.embedding_service.invalidate_for_conversation(conversation_id)
            return
        from app.ai.rag.pgvector_store import PgVectorStore
        from app.repositories.embedding import EmbeddingJobRepository, EmbeddingUsageRepository

        await PgVectorStore(self.session).delete_for_conversation(conversation_id)
        await EmbeddingJobRepository(self.session).delete_for_conversation(conversation_id)
        await EmbeddingUsageRepository(self.session).delete_for_conversation(conversation_id)


def _validate_import_upload(upload: UploadFile) -> None:
    filename = (upload.filename or "").lower()
    if not (filename.endswith(".txt") or filename.endswith(".zip")):
        raise BadRequestError("Envie um arquivo .txt ou .zip exportado do WhatsApp")

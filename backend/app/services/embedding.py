from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.provider import EmbeddingProvider
from app.ai.rag.types import EmbeddingJobStatus
from app.ai.rag.vector_store import EmbeddingRecord, VectorStore
from app.conversation.chunker import chunk_messages
from app.conversation.metric_message import MetricMessage
from app.conversation.types import MessageType
from app.core.config import Settings
from app.models.embedding import ConversationEmbeddingJob
from app.models.embedding_usage import EmbeddingUsageRecord
from app.repositories.conversation import ConversationRepository
from app.repositories.embedding import EmbeddingJobRepository, EmbeddingUsageRepository
from app.repositories.message import MessageRepository, ParticipantRepository
from app.services.embedding_jobs import EmbeddingJobEnqueuer, EmbeddingReadiness
from app.services.usage import record_embedding_usage


class EmbeddingGenerationService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        job_enqueuer: EmbeddingJobEnqueuer,
    ) -> None:
        self.session = session
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.job_enqueuer = job_enqueuer
        self.jobs = EmbeddingJobRepository(session)
        self.usage = EmbeddingUsageRepository(session)
        self.messages = MessageRepository(session)
        self.participants = ParticipantRepository(session)

    async def ensure_ready(self, conversation_id: UUID) -> EmbeddingReadiness:
        job = await self.jobs.get_for_conversation(conversation_id)
        count = await self.vector_store.count_for_conversation(conversation_id)
        if job and job.status == EmbeddingJobStatus.COMPLETED and count > 0:
            return EmbeddingReadiness(True, EmbeddingJobStatus.COMPLETED, "Embeddings prontos.")
        if job and job.status == EmbeddingJobStatus.PROCESSING:
            return EmbeddingReadiness(
                False,
                EmbeddingJobStatus.PROCESSING,
                "Embeddings em processamento. Tente novamente em instantes.",
            )
        if job and job.status == EmbeddingJobStatus.PENDING:
            return EmbeddingReadiness(
                False,
                EmbeddingJobStatus.PENDING,
                "Embeddings aguardando processamento.",
            )
        await self._mark_pending(conversation_id)
        await self.job_enqueuer.enqueue_generate_embeddings(conversation_id)
        return EmbeddingReadiness(
            False,
            EmbeddingJobStatus.PENDING,
            "Geração de embeddings iniciada. Tente novamente em instantes.",
        )

    async def generate_for_conversation(self, conversation_id: UUID) -> None:
        job = await self.jobs.get_for_conversation(conversation_id)
        if job is None:
            job = ConversationEmbeddingJob(
                conversation_id=conversation_id,
                status=EmbeddingJobStatus.PROCESSING,
            )
        else:
            job.status = EmbeddingJobStatus.PROCESSING
            job.error_message = None
        await self.jobs.upsert(job)
        await self.session.commit()

        try:
            metric_messages = await self._load_metric_messages(conversation_id)
            chunks = chunk_messages(
                conversation_id,
                metric_messages,
                chunk_size=self.settings.rag_chunk_size,
            )
            await self.vector_store.delete_for_conversation(conversation_id)
            total_tokens = 0
            stored = 0
            model_name = self.settings.embedding_model
            provider_name = self.settings.embedding_provider
            if not chunks:
                completed = ConversationEmbeddingJob(
                    conversation_id=conversation_id,
                    status=EmbeddingJobStatus.COMPLETED,
                    chunks_embedded=0,
                    tokens_embedded=0,
                    embedding_model=model_name,
                )
                await self.jobs.upsert(completed)
                await self.session.commit()
                return

            batch_size = self.settings.embedding_batch_size
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start : start + batch_size]
                texts = [item.chunk_text for item in batch]
                embedded = await self.embedding_provider.embed_texts(texts)
                total_tokens += embedded.usage.input_tokens
                model_name = embedded.usage.model
                provider_name = embedded.usage.provider
                records = [
                    EmbeddingRecord(
                        id=uuid4(),
                        conversation_id=conversation_id,
                        message_ids=item.message_ids,
                        chunk_text=item.chunk_text,
                        vector=vector,
                        metadata=item.metadata,
                    )
                    for item, vector in zip(batch, embedded.vectors, strict=True)
                ]
                stored += await self.vector_store.store(records)

            completed = ConversationEmbeddingJob(
                conversation_id=conversation_id,
                status=EmbeddingJobStatus.COMPLETED,
                chunks_embedded=stored,
                tokens_embedded=total_tokens,
                embedding_model=model_name,
            )
            await self.jobs.upsert(completed)
            await self.usage.upsert(
                EmbeddingUsageRecord(
                    conversation_id=conversation_id,
                    chunks_embedded=stored,
                    tokens_embedded=total_tokens,
                    embedding_model=model_name,
                    embedding_provider=provider_name,
                )
            )
            conv = await ConversationRepository(self.session).get_by_id(conversation_id)
            if conv:
                from app.ai.embeddings.provider import EmbeddingUsage

                await record_embedding_usage(
                    self.session,
                    user_id=conv.user_id,
                    conversation_id=conversation_id,
                    operation="embeddings",
                    usage=EmbeddingUsage(
                        input_tokens=total_tokens,
                        model=model_name,
                        provider=provider_name,
                    ),
                )
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            failed = ConversationEmbeddingJob(
                conversation_id=conversation_id,
                status=EmbeddingJobStatus.FAILED,
                error_message=str(exc),
            )
            await self.jobs.upsert(failed)
            await self.session.commit()
            raise

    async def invalidate_for_conversation(self, conversation_id: UUID) -> None:
        await self.vector_store.delete_for_conversation(conversation_id)
        await self.jobs.delete_for_conversation(conversation_id)
        await self.usage.delete_for_conversation(conversation_id)

    async def _mark_pending(self, conversation_id: UUID) -> None:
        await self.jobs.upsert(
            ConversationEmbeddingJob(
                conversation_id=conversation_id,
                status=EmbeddingJobStatus.PENDING,
            )
        )
        await self.session.commit()

    async def _load_metric_messages(self, conversation_id: UUID) -> list[MetricMessage]:
        participants = await self.participants.list_for_conversation(conversation_id)
        names = {item.id: item.name for item in participants}
        rows = await self.messages.list_all_for_conversation(conversation_id)
        return [
            MetricMessage(
                id=row.id,
                sender_id=row.sender_id,
                sender_name=names.get(row.sender_id) if row.sender_id else None,
                timestamp=row.timestamp,
                message_type=MessageType(row.type),
                content=row.content,
            )
            for row in rows
        ]

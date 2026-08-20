from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import ConversationEmbeddingJob
from app.models.embedding_usage import EmbeddingUsageRecord


class EmbeddingJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_conversation(self, conversation_id: UUID) -> ConversationEmbeddingJob | None:
        stmt = select(ConversationEmbeddingJob).where(
            ConversationEmbeddingJob.conversation_id == conversation_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, job: ConversationEmbeddingJob) -> ConversationEmbeddingJob:
        existing = await self.get_for_conversation(job.conversation_id)
        if existing is None:
            self.session.add(job)
            await self.session.flush()
            await self.session.refresh(job)
            return job
        existing.status = job.status
        existing.chunks_embedded = job.chunks_embedded
        existing.tokens_embedded = job.tokens_embedded
        existing.embedding_model = job.embedding_model
        existing.error_message = job.error_message
        await self.session.flush()
        await self.session.refresh(existing)
        return existing

    async def delete_for_conversation(self, conversation_id: UUID) -> None:
        await self.session.execute(
            delete(ConversationEmbeddingJob).where(
                ConversationEmbeddingJob.conversation_id == conversation_id
            )
        )


class EmbeddingUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, record: EmbeddingUsageRecord) -> EmbeddingUsageRecord:
        stmt = select(EmbeddingUsageRecord).where(
            EmbeddingUsageRecord.conversation_id == record.conversation_id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            self.session.add(record)
            await self.session.flush()
            await self.session.refresh(record)
            return record
        existing.chunks_embedded = record.chunks_embedded
        existing.tokens_embedded = record.tokens_embedded
        existing.embedding_model = record.embedding_model
        existing.embedding_provider = record.embedding_provider
        await self.session.flush()
        await self.session.refresh(existing)
        return existing

    async def delete_for_conversation(self, conversation_id: UUID) -> None:
        await self.session.execute(
            delete(EmbeddingUsageRecord).where(
                EmbeddingUsageRecord.conversation_id == conversation_id
            )
        )

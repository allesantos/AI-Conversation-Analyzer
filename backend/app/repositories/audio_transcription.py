from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_transcription import AudioTranscription


class AudioTranscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, row: AudioTranscription) -> AudioTranscription:
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get_by_id(self, transcription_id: UUID) -> AudioTranscription | None:
        stmt = select(AudioTranscription).where(AudioTranscription.id == transcription_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_conversation(
        self,
        transcription_id: UUID,
        conversation_id: UUID,
    ) -> AudioTranscription | None:
        stmt = select(AudioTranscription).where(
            AudioTranscription.id == transcription_id,
            AudioTranscription.conversation_id == conversation_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_message(self, message_id: UUID) -> AudioTranscription | None:
        stmt = (
            select(AudioTranscription)
            .where(AudioTranscription.message_id == message_id)
            .order_by(AudioTranscription.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_completed_by_file_hash(
        self,
        conversation_id: UUID,
        file_hash: str,
    ) -> AudioTranscription | None:
        stmt = (
            select(AudioTranscription)
            .where(
                AudioTranscription.conversation_id == conversation_id,
                AudioTranscription.file_hash == file_hash,
                AudioTranscription.status == "COMPLETED",
                AudioTranscription.transcribed_text.is_not(None),
            )
            .order_by(AudioTranscription.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, row: AudioTranscription) -> AudioTranscription:
        await self.session.flush()
        await self.session.refresh(row)
        return row

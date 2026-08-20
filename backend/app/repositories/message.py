from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.participant import Participant


class ParticipantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_conversation(self, conversation_id: UUID) -> list[Participant]:
        stmt = (
            select(Participant)
            .where(Participant.conversation_id == conversation_id)
            .order_by(Participant.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_insert(self, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        await self.session.execute(insert(Participant), rows)

    async def get_by_id(
        self,
        conversation_id: UUID,
        participant_id: UUID,
    ) -> Participant | None:
        stmt = select(Participant).where(
            Participant.conversation_id == conversation_id,
            Participant.id == participant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, row: Participant) -> Participant:
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def delete_for_conversation(self, conversation_id: UUID) -> None:
        await self.session.execute(
            delete(Participant).where(Participant.conversation_id == conversation_id)
        )


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_page(self, conversation_id: UUID, *, offset: int, limit: int) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc(), Message.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_conversation(self, conversation_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def bulk_insert(self, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        await self.session.execute(insert(Message), rows)

    async def delete_for_conversation(self, conversation_id: UUID) -> None:
        await self.session.execute(
            delete(Message).where(Message.conversation_id == conversation_id)
        )

    async def list_all_for_conversation(self, conversation_id: UUID) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc(), Message.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(
        self,
        conversation_id: UUID,
        message_ids: list[UUID],
    ) -> list[Message]:
        if not message_ids:
            return []
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.id.in_(message_ids),
            )
            .order_by(Message.timestamp.asc(), Message.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, conversation_id: UUID, message_id: UUID) -> Message | None:
        stmt = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.id == message_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_id(self, conversation_id: UUID, message_id: UUID) -> bool:
        stmt = delete(Message).where(
            Message.conversation_id == conversation_id,
            Message.id == message_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def list_analysis_only(self, conversation_id: UUID) -> list[Message]:
        rows = await self.list_all_for_conversation(conversation_id)
        return [
            row
            for row in rows
            if isinstance(row.message_metadata, dict)
            and row.message_metadata.get("analysis_only") is True
        ]

    async def add(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def update_content(
        self,
        message: Message,
        *,
        content: str,
        metadata: dict[str, object],
        message_type: str | None = None,
    ) -> Message:
        message.content = content
        message.message_metadata = metadata
        if message_type is not None:
            message.type = message_type
        await self.session.flush()
        await self.session.refresh(message)
        return message

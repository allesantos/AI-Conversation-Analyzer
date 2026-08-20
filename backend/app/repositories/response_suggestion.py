from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.response_suggestion import ResponseSuggestion


class ResponseSuggestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_conversation(
        self,
        conversation_id: UUID,
        rows: list[ResponseSuggestion],
    ) -> list[ResponseSuggestion]:
        await self.session.execute(
            delete(ResponseSuggestion).where(ResponseSuggestion.conversation_id == conversation_id)
        )
        for row in rows:
            self.session.add(row)
        await self.session.flush()
        for row in rows:
            await self.session.refresh(row)
        return rows

    async def list_for_conversation(self, conversation_id: UUID) -> list[ResponseSuggestion]:
        stmt = (
            select(ResponseSuggestion)
            .where(ResponseSuggestion.conversation_id == conversation_id)
            .order_by(ResponseSuggestion.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

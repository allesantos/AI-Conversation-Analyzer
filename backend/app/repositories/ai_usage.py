from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_usage import AIUsage


class AIUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: AIUsage) -> AIUsage:
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_for_user(self, user_id: UUID) -> list[AIUsage]:
        result = await self.session.execute(
            select(AIUsage).where(AIUsage.user_id == user_id).order_by(AIUsage.created_at.desc())
        )
        return list(result.scalars().all())

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.interest_engine.types import InterestLevel
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.ai_usage import AIUsageRepository
from app.schemas.dashboard import DashboardConversationItem, DashboardSummary
from app.schemas.usage import UsageRecord, UsageSummary


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_summary(self, user_id: UUID, *, recent_limit: int = 8) -> DashboardSummary:
        conversations = await self._list_conversations(user_id)
        message_counts = await self._message_counts([c.id for c in conversations])

        distribution = {level.value: 0 for level in InterestLevel}
        analyzed = 0
        items: list[DashboardConversationItem] = []

        for conversation in conversations:
            analysis = conversation.analysis
            interest_level = analysis.interest_level if analysis else None
            if analysis and analysis.interest_level:
                analyzed += 1
                if interest_level in distribution:
                    distribution[interest_level] += 1

            items.append(
                DashboardConversationItem(
                    id=conversation.id,
                    title=conversation.title,
                    updated_at=conversation.updated_at,
                    total_messages=message_counts.get(conversation.id, 0),
                    interest_level=interest_level,
                    interest_score=analysis.interest_score if analysis else None,
                    confidence_score=analysis.confidence_score if analysis else None,
                    analyzed_at=analysis.updated_at if analysis else None,
                )
            )

        items.sort(
            key=lambda item: item.analyzed_at or item.updated_at,
            reverse=True,
        )
        recent = items[:recent_limit]
        usage = await self._usage_summary(user_id)

        return DashboardSummary(
            total_conversations=len(conversations),
            analyzed_conversations=analyzed,
            interest_distribution=distribution,
            recent=recent,
            usage=usage,
        )

    async def _list_conversations(self, user_id: UUID) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .options(selectinload(Conversation.analysis))
            .order_by(Conversation.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def _message_counts(self, conversation_ids: list[UUID]) -> dict[UUID, int]:
        if not conversation_ids:
            return {}
        stmt = (
            select(Message.conversation_id, func.count())
            .where(Message.conversation_id.in_(conversation_ids))
            .group_by(Message.conversation_id)
        )
        result = await self.session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def _usage_summary(self, user_id: UUID) -> UsageSummary:
        rows = await AIUsageRepository(self.session).list_for_user(user_id)
        records = [UsageRecord.model_validate(r) for r in rows]
        return UsageSummary(
            total_records=len(records),
            total_input_tokens=sum(r.input_tokens for r in records),
            total_output_tokens=sum(r.output_tokens for r in records),
            total_audio_seconds=sum(r.audio_seconds or 0 for r in records),
            total_estimated_cost=round(sum(r.estimated_cost for r in records), 6),
            records=[],  # dashboard só precisa dos totais
        )

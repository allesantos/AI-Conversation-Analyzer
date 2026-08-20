from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_analysis import AnalysisEvidence, ConversationAnalysis


class ConversationAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_conversation(self, conversation_id: UUID) -> ConversationAnalysis | None:
        stmt = select(ConversationAnalysis).where(
            ConversationAnalysis.conversation_id == conversation_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_for_conversation(self, conversation_id: UUID) -> None:
        await self.session.execute(
            delete(ConversationAnalysis).where(
                ConversationAnalysis.conversation_id == conversation_id
            )
        )

    async def upsert(self, analysis: ConversationAnalysis) -> ConversationAnalysis:
        existing = await self.get_for_conversation(analysis.conversation_id)
        if existing is None:
            self.session.add(analysis)
            await self.session.flush()
            await self.session.refresh(analysis)
            return analysis
        existing.summary = analysis.summary
        existing.metrics = analysis.metrics
        existing.llm_provider = analysis.llm_provider
        existing.llm_model = analysis.llm_model
        existing.input_tokens = analysis.input_tokens
        existing.output_tokens = analysis.output_tokens
        existing.interest_score = analysis.interest_score
        existing.interest_level = analysis.interest_level
        existing.confidence_score = analysis.confidence_score
        existing.positive_signals = analysis.positive_signals
        existing.neutral_signals = analysis.neutral_signals
        existing.negative_signals = analysis.negative_signals
        await self.session.flush()
        await self.session.refresh(existing)
        return existing


class AnalysisEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_analysis(
        self,
        analysis_id: UUID,
        rows: list[AnalysisEvidence],
    ) -> None:
        await self.session.execute(
            delete(AnalysisEvidence).where(AnalysisEvidence.conversation_analysis_id == analysis_id)
        )
        for row in rows:
            self.session.add(row)
        await self.session.flush()

    async def list_for_analysis(self, analysis_id: UUID) -> list[AnalysisEvidence]:
        stmt = (
            select(AnalysisEvidence)
            .where(AnalysisEvidence.conversation_analysis_id == analysis_id)
            .order_by(AnalysisEvidence.signal_key)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

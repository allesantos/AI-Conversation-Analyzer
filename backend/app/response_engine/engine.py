from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.provider import LLMProvider
from app.ai.prompts.loader import load_prompt
from app.ai.rag.strategy import determine_context_strategy
from app.ai.rag.types import ContextStrategy
from app.conversation.context_builder import (
    build_direct_context,
    build_intermediate_context,
    build_rag_context,
)
from app.conversation.metric_message import MetricMessage
from app.conversation.metrics import calculate_conversation_metrics
from app.conversation.types import MessageType
from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError, ProcessingError
from app.models.response_suggestion import ResponseSuggestion
from app.repositories.analysis import ConversationAnalysisRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository, ParticipantRepository
from app.repositories.response_suggestion import ResponseSuggestionRepository
from app.response_engine.schemas import ResponseSuggestionsOutput
from app.schemas.suggestion import SuggestionRead, SuggestionsResponse
from app.services.embedding import EmbeddingGenerationService
from app.services.usage import record_llm_usage

EXPECTED_CATEGORIES = ("NATURAL", "DIVERTIDA", "DIRETA", "CONSERVADORA")


class ResponseEngine:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        llm: LLMProvider,
        embedding_service: EmbeddingGenerationService,
    ) -> None:
        self.session = session
        self.settings = settings
        self.llm = llm
        self.embedding_service = embedding_service
        self.conversations = ConversationRepository(session)
        self.participants = ParticipantRepository(session)
        self.messages = MessageRepository(session)
        self.analyses = ConversationAnalysisRepository(session)
        self.suggestions_repo = ResponseSuggestionRepository(session)

    async def generate(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        incoming_message: str,
    ) -> SuggestionsResponse:
        conversation = await self._owned(conversation_id, user_id)
        pasted = incoming_message.strip()
        if not pasted:
            raise BadRequestError("Cole a mensagem recebida no WhatsApp.")

        metric_messages = await self._load_metric_messages(conversation.id)
        analyzable = [
            m
            for m in metric_messages
            if m.message_type not in (MessageType.SYSTEM,) and m.content.strip()
        ]
        if len(analyzable) < 1:
            raise BadRequestError(
                "Importe o histórico da conversa antes de gerar sugestões "
                "(o contexto é necessário)."
            )

        strategy = determine_context_strategy(len(metric_messages), self.settings)
        metrics = calculate_conversation_metrics(
            metric_messages,
            gap_hours=self.settings.conversation_gap_hours,
        )
        context = await self._build_context(
            conversation.id,
            metric_messages,
            strategy,
            retrieval_query=pasted,
        )

        existing_analysis = await self.analyses.get_for_conversation(conversation.id)
        interest_block = ""
        if existing_analysis and existing_analysis.interest_level:
            interest_block = (
                f"\nNível de reciprocidade pré-calculado: "
                f"{existing_analysis.interest_level} "
                f"(confiança {existing_analysis.confidence_score}%). "
                "Considere isso ao calibrar o tom das sugestões.\n"
            )

        system_prompt = load_prompt("responses/suggestions_system.txt")
        user_prompt = _build_user_prompt(
            incoming_message=pasted,
            metrics=metrics,
            context=context,
            strategy=strategy,
            interest_block=interest_block,
        )

        result = await self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ResponseSuggestionsOutput,
        )
        output = result.data
        assert isinstance(output, ResponseSuggestionsOutput)

        await record_llm_usage(
            self.session,
            user_id=user_id,
            conversation_id=conversation.id,
            operation="suggestions",
            usage=result.usage,
        )

        rows: list[ResponseSuggestion] = []
        for item in output.suggestions:
            rows.append(
                ResponseSuggestion(
                    conversation_id=conversation.id,
                    category=item.category.upper(),
                    suggested_text=item.text,
                    based_on_message_id=None,
                )
            )
        saved = await self.suggestions_repo.replace_for_conversation(conversation.id, rows)
        await self.session.commit()

        return SuggestionsResponse(
            conversation_id=conversation.id,
            based_on_message_id=None,
            incoming_message=pasted,
            suggestions=[
                SuggestionRead(
                    id=row.id,
                    category=row.category,
                    suggested_text=row.suggested_text,
                    created_at=row.created_at,
                )
                for row in saved
            ],
            llm_provider=result.usage.provider,
            llm_model=result.usage.model,
        )

    async def _build_context(
        self,
        conversation_id: UUID,
        metric_messages: list[MetricMessage],
        strategy: ContextStrategy,
        *,
        retrieval_query: str,
    ) -> str:
        if strategy is ContextStrategy.DIRECT:
            return build_direct_context(
                metric_messages,
                max_messages=self.settings.rag_direct_max_messages,
            )
        if strategy is ContextStrategy.SUMMARY_SELECTION:
            return build_intermediate_context(metric_messages, self.settings)
        readiness = await self.embedding_service.ensure_ready(conversation_id)
        if not readiness.ready:
            raise ProcessingError(readiness.message, processing_status=readiness.status)
        from app.ai.rag.retriever import ConversationRetriever

        retriever = ConversationRetriever(
            vector_store=self.embedding_service.vector_store,
            embedding_provider=self.embedding_service.embedding_provider,
            top_k=self.settings.rag_top_k,
        )
        retrieved = await retriever.retrieve(conversation_id, retrieval_query)
        existing = await self.analyses.get_for_conversation(conversation_id)
        return build_rag_context(
            metrics=calculate_conversation_metrics(
                metric_messages,
                gap_hours=self.settings.conversation_gap_hours,
            ),
            summary=existing.summary if existing else None,
            retrieved=retrieved,
        )

    async def _load_metric_messages(self, conversation_id: UUID) -> list[MetricMessage]:
        participants = await self.participants.list_for_conversation(conversation_id)
        names = {item.id: item.name for item in participants}
        rows = await self.messages.list_all_for_conversation(conversation_id)
        return [
            MetricMessage(
                id=row.id,
                sender_id=row.sender_id,
                sender_name=(names.get(row.sender_id) if row.sender_id else None),
                timestamp=row.timestamp,
                message_type=MessageType(row.type),
                content=row.content,
            )
            for row in rows
        ]

    async def _owned(self, conversation_id: UUID, user_id: UUID):
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada")
        return conversation


def _build_user_prompt(
    *,
    incoming_message: str,
    metrics: dict[str, object],
    context: str,
    strategy: ContextStrategy,
    interest_block: str,
) -> str:
    avg_lengths = metrics.get("average_message_length_by_participant", {})
    style_hints = ""
    if isinstance(avg_lengths, dict) and avg_lengths:
        style_hints = (
            "Tamanho médio de mensagem por participante: "
            + ", ".join(f"{name}: {length} caracteres" for name, length in avg_lengths.items())
            + "\n"
        )

    return (
        f"Estratégia de contexto: {strategy.value}\n"
        f"{style_hints}"
        f"{interest_block}\n"
        f"Mensagem recebida AGORA (colar do WhatsApp — responder a isto):\n"
        f"{incoming_message}\n\n"
        f"Métricas do histórico importado (JSON):\n"
        f"{json.dumps(metrics, ensure_ascii=False, indent=2)}\n\n"
        f"Contexto do histórico importado:\n{context}\n\n"
        f"Gere exatamente 4 sugestões de resposta "
        f"(NATURAL, DIVERTIDA, DIRETA, CONSERVADORA)."
    )

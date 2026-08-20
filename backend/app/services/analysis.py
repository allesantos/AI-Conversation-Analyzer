from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.provider import LLMProvider
from app.ai.llm.schemas import AskAnswerOutput, ConversationSummaryOutput
from app.ai.prompts.loader import load_prompt
from app.ai.rag.retriever import ConversationRetriever
from app.ai.rag.strategy import determine_context_strategy
from app.ai.rag.types import ContextStrategy
from app.conversation.analysis_fingerprint import compute_analysis_fingerprint
from app.conversation.context_builder import (
    build_direct_context,
    build_intermediate_context,
    build_rag_context,
)
from app.conversation.metric_message import MetricMessage
from app.conversation.metrics import calculate_conversation_metrics
from app.conversation.types import MessageType, ParticipantRole
from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError, ProcessingError
from app.interest_engine.evidence_builder import signals_for_storage
from app.interest_engine.participants import resolve_analysis_participants
from app.interest_engine.timeline_analyzer import analyze_timeline, run_interest_analysis
from app.interest_engine.types import ClassifiedSignal, InterestAssessment
from app.models.conversation_analysis import AnalysisEvidence, ConversationAnalysis
from app.models.participant import Participant
from app.repositories.analysis import AnalysisEvidenceRepository, ConversationAnalysisRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository, ParticipantRepository
from app.schemas.analysis import (
    AnalysisRead,
    AnalyzeResponse,
    AskResponse,
    EvidenceRead,
    SignalRead,
    TimelinePeriodRead,
    TimelineRead,
)
from app.services.embedding import EmbeddingGenerationService
from app.services.usage import record_llm_usage

_RAG_ANALYZE_QUERY = "Resumo geral da conversa, principais temas e dinâmica entre participantes"


class AnalysisService:
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
        self.evidence = AnalysisEvidenceRepository(session)

    async def analyze(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        force: bool = False,
    ) -> AnalyzeResponse:
        conversation = await self._owned(conversation_id, user_id)
        participant_rows = await self.participants.list_for_conversation(conversation.id)
        self._require_owner(participant_rows)
        owner_name, other_name = resolve_analysis_participants(participant_rows)
        metric_messages = await self._load_metric_messages(conversation.id)
        fingerprint = compute_analysis_fingerprint(metric_messages)

        existing = await self.analyses.get_for_conversation(conversation.id)
        if (
            not force
            and existing is not None
            and self._llm_cache_is_valid(existing.metrics, fingerprint)
        ):
            return await self._build_stored_response(existing, from_cache=True)

        strategy = determine_context_strategy(len(metric_messages), self.settings)
        metrics = self._build_metrics(metric_messages)
        interest = run_interest_analysis(
            metric_messages,
            metrics,
            owner_name=owner_name,
            other_name=other_name,
            gap_hours=self.settings.conversation_gap_hours,
        )
        context = await self._build_context(
            conversation.id,
            metric_messages,
            strategy,
            query=_RAG_ANALYZE_QUERY,
            existing_summary=existing.summary if existing else None,
        )

        system_prompt = load_prompt("analysis/summary_system.txt")
        user_prompt = _build_summary_user_prompt(
            title=conversation.title,
            metrics=metrics,
            context=context,
            strategy=strategy,
            interest=interest,
            owner_name=owner_name,
            other_name=other_name,
        )
        result = await self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ConversationSummaryOutput,
        )
        summary_output = result.data
        assert isinstance(summary_output, ConversationSummaryOutput)

        await record_llm_usage(
            self.session,
            user_id=user_id,
            conversation_id=conversation.id,
            operation="analyze",
            usage=result.usage,
        )

        metrics["context_strategy"] = strategy.value
        metrics["observations"] = summary_output.observations
        metrics["inferences"] = summary_output.inferences
        metrics["reciprocity"] = _reciprocity_payload(interest)
        metrics["content_fingerprint"] = fingerprint
        metrics["llm_content_fingerprint"] = fingerprint
        metrics["summary_stale"] = False
        stored = await self.analyses.upsert(
            ConversationAnalysis(
                conversation_id=conversation.id,
                summary=summary_output.summary,
                metrics=metrics,
                llm_provider=result.usage.provider,
                llm_model=result.usage.model,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                interest_score=interest.interest_score,
                interest_level=interest.interest_level.value,
                confidence_score=interest.confidence_score,
                positive_signals=signals_for_storage(list(interest.positive_signals)),
                neutral_signals=signals_for_storage(list(interest.neutral_signals)),
                negative_signals=signals_for_storage(list(interest.negative_signals)),
            )
        )
        evidence_rows = [
            AnalysisEvidence(
                conversation_analysis_id=stored.id,
                signal_key=record.signal_key.value,
                signal_label=record.signal_label,
                polarity=record.polarity.value,
                message_ids=[str(message_id) for message_id in record.message_ids],
                observation=record.observation,
            )
            for record in interest.evidence
        ]
        await self.evidence.replace_for_analysis(stored.id, evidence_rows)
        await self.session.commit()

        return await self._build_stored_response(stored, from_cache=False)

    async def refresh_derived_analysis(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> AnalyzeResponse | None:
        """Recalcula métricas, sinais e evidências localmente, sem chamar o LLM."""
        conversation = await self._owned(conversation_id, user_id)
        existing = await self.analyses.get_for_conversation(conversation.id)
        if existing is None:
            return None

        participant_rows = await self.participants.list_for_conversation(conversation.id)
        owner_name, other_name = resolve_analysis_participants(participant_rows)
        metric_messages = await self._load_metric_messages(conversation.id)
        if not metric_messages:
            return None

        strategy = determine_context_strategy(len(metric_messages), self.settings)
        metrics = self._build_metrics(metric_messages)
        interest = run_interest_analysis(
            metric_messages,
            metrics,
            owner_name=owner_name,
            other_name=other_name,
            gap_hours=self.settings.conversation_gap_hours,
        )
        fingerprint = compute_analysis_fingerprint(metric_messages)
        stored_metrics = dict(existing.metrics or {})
        stored_metrics.update(metrics)
        stored_metrics["context_strategy"] = strategy.value
        stored_metrics["reciprocity"] = _reciprocity_payload(interest)
        stored_metrics["content_fingerprint"] = fingerprint
        llm_fingerprint = stored_metrics.get("llm_content_fingerprint")
        stored_metrics["summary_stale"] = (
            not isinstance(llm_fingerprint, str) or llm_fingerprint != fingerprint
        )

        existing.metrics = stored_metrics
        existing.interest_score = interest.interest_score
        existing.interest_level = interest.interest_level.value
        existing.confidence_score = interest.confidence_score
        existing.positive_signals = signals_for_storage(list(interest.positive_signals))
        existing.neutral_signals = signals_for_storage(list(interest.neutral_signals))
        existing.negative_signals = signals_for_storage(list(interest.negative_signals))
        stored = await self.analyses.upsert(existing)

        evidence_rows = [
            AnalysisEvidence(
                conversation_analysis_id=stored.id,
                signal_key=record.signal_key.value,
                signal_label=record.signal_label,
                polarity=record.polarity.value,
                message_ids=[str(message_id) for message_id in record.message_ids],
                observation=record.observation,
            )
            for record in interest.evidence
        ]
        await self.evidence.replace_for_analysis(stored.id, evidence_rows)
        await self.session.commit()
        return await self._build_stored_response(stored, from_cache=False)

    async def reconcile_after_import(self, conversation_id: UUID, user_id: UUID) -> None:
        """Reconcilia análise existente após reimportação (novos IDs, mesmo conteúdo possível)."""
        await self._owned(conversation_id, user_id)
        existing = await self.analyses.get_for_conversation(conversation_id)
        if existing is None:
            return

        metric_messages = await self._load_metric_messages(conversation_id)
        if not metric_messages:
            await self.analyses.delete_for_conversation(conversation_id)
            await self.session.commit()
            return

        fingerprint = compute_analysis_fingerprint(metric_messages)
        stored_metrics = dict(existing.metrics or {})
        llm_fingerprint = stored_metrics.get("llm_content_fingerprint")
        stored_metrics["content_fingerprint"] = fingerprint
        stored_metrics["summary_stale"] = (
            not isinstance(llm_fingerprint, str) or llm_fingerprint != fingerprint
        )
        existing.metrics = stored_metrics
        await self.analyses.upsert(existing)
        await self.session.commit()
        await self.refresh_derived_analysis(conversation_id, user_id)

    async def get_analysis(self, conversation_id: UUID, user_id: UUID) -> AnalyzeResponse:
        await self._owned(conversation_id, user_id)
        analysis = await self.analyses.get_for_conversation(conversation_id)
        if analysis is None:
            raise NotFoundError("Análise não encontrada. Execute a análise primeiro.")
        return await self._build_stored_response(analysis, from_cache=False)

    async def _build_stored_response(
        self,
        analysis: ConversationAnalysis,
        *,
        from_cache: bool,
    ) -> AnalyzeResponse:
        metrics = analysis.metrics or {}
        evidence_read = await self._load_evidence_read(analysis.id)
        return AnalyzeResponse(
            analysis=AnalysisRead.model_validate(analysis),
            observations=_metrics_string_list(metrics, "observations"),
            inferences=_metrics_string_list(metrics, "inferences"),
            context_strategy=str(metrics.get("context_strategy", "")),
            interest_score=analysis.interest_score,
            interest_level=analysis.interest_level,
            confidence_score=analysis.confidence_score,
            positive_signals=_stored_signals_to_read(analysis.positive_signals),
            neutral_signals=_stored_signals_to_read(analysis.neutral_signals),
            negative_signals=_stored_signals_to_read(analysis.negative_signals),
            evidence=evidence_read,
            reciprocity=metrics.get("reciprocity")
            if isinstance(metrics.get("reciprocity"), dict)
            else None,
            summary_stale=bool(metrics.get("summary_stale")),
            from_cache=from_cache,
        )

    @staticmethod
    def _llm_cache_is_valid(metrics: dict[str, object] | None, fingerprint: str) -> bool:
        if not metrics:
            return False
        content_fp = metrics.get("content_fingerprint")
        llm_fp = metrics.get("llm_content_fingerprint")
        if content_fp != fingerprint or llm_fp != fingerprint:
            return False
        return not bool(metrics.get("summary_stale"))

    async def get_timeline(self, conversation_id: UUID, user_id: UUID) -> TimelineRead:
        conversation = await self._owned(conversation_id, user_id)
        participant_rows = await self.participants.list_for_conversation(conversation.id)
        owner_name, other_name = resolve_analysis_participants(participant_rows)
        metric_messages = await self._load_metric_messages(conversation.id)
        if not metric_messages:
            raise BadRequestError("A conversa não possui mensagens para timeline.")
        periods = analyze_timeline(
            metric_messages,
            owner_name=owner_name,
            other_name=other_name,
            gap_hours=self.settings.conversation_gap_hours,
        )
        return TimelineRead(
            conversation_id=conversation.id,
            periods=[
                TimelinePeriodRead(
                    key=item.key,
                    label=item.label,
                    message_count=item.message_count,
                    interest_score=item.interest_score,
                    interest_level=item.interest_level.value,
                    confidence_score=item.confidence_score,
                    positive_count=item.positive_count,
                    neutral_count=item.neutral_count,
                    negative_count=item.negative_count,
                    summary_observation=item.summary_observation,
                )
                for item in periods
            ],
        )

    async def ask(
        self,
        conversation_id: UUID,
        user_id: UUID,
        question: str,
    ) -> AskResponse:
        conversation = await self._owned(conversation_id, user_id)
        metric_messages = await self._load_metric_messages(conversation.id)
        strategy = determine_context_strategy(len(metric_messages), self.settings)
        metrics = self._build_metrics(metric_messages)
        existing = await self.analyses.get_for_conversation(conversation.id)
        context = await self._build_context(
            conversation.id,
            metric_messages,
            strategy,
            query=question.strip(),
            existing_summary=existing.summary if existing else None,
        )

        system_prompt = load_prompt("analysis/ask_system.txt")
        user_prompt = _build_ask_user_prompt(
            title=conversation.title,
            question=question.strip(),
            metrics=metrics,
            context=context,
            existing_summary=existing.summary if existing else None,
            strategy=strategy,
            existing_analysis=existing,
        )
        result = await self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=AskAnswerOutput,
        )
        answer_output = result.data
        assert isinstance(answer_output, AskAnswerOutput)

        await record_llm_usage(
            self.session,
            user_id=user_id,
            conversation_id=conversation.id,
            operation="ask",
            usage=result.usage,
        )
        await self.session.commit()

        return AskResponse(
            answer=answer_output.answer,
            observations=answer_output.observations,
            inferences=answer_output.inferences,
            llm_provider=result.usage.provider,
            llm_model=result.usage.model,
            context_strategy=strategy.value,
        )

    async def _load_evidence_read(self, analysis_id: UUID) -> list[EvidenceRead]:
        rows = await self.evidence.list_for_analysis(analysis_id)
        return [
            EvidenceRead(
                id=row.id,
                signal_key=row.signal_key,
                signal_label=row.signal_label,
                polarity=row.polarity,
                message_ids=[UUID(value) for value in row.message_ids],
                observation=row.observation,
            )
            for row in rows
        ]

    async def _build_context(
        self,
        conversation_id: UUID,
        metric_messages: list[MetricMessage],
        strategy: ContextStrategy,
        *,
        query: str,
        existing_summary: str | None,
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
        retriever = ConversationRetriever(
            vector_store=self.embedding_service.vector_store,
            embedding_provider=self.embedding_service.embedding_provider,
            top_k=self.settings.rag_top_k,
        )
        retrieved = await retriever.retrieve(conversation_id, query)
        metrics = self._build_metrics(metric_messages)
        return build_rag_context(
            metrics=metrics,
            summary=existing_summary,
            retrieved=retrieved,
        )

    def _build_metrics(self, metric_messages: list[MetricMessage]) -> dict[str, object]:
        metrics = calculate_conversation_metrics(
            metric_messages,
            gap_hours=self.settings.conversation_gap_hours,
        )
        if metrics["total_analyzable_messages"] == 0:
            raise BadRequestError("A conversa não possui mensagens analisáveis.")
        return metrics

    @staticmethod
    def _require_owner(participants: list[Participant]) -> None:
        if not participants:
            raise BadRequestError("Importe a conversa antes de analisar.")
        if any(item.role == ParticipantRole.OWNER.value for item in participants):
            return
        raise BadRequestError(
            "Defina quem é você na conversa antes de analisar (escolha o seu nome)."
        )

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

    async def _owned(self, conversation_id: UUID, user_id: UUID):
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada")
        return conversation


def _build_summary_user_prompt(
    *,
    title: str,
    metrics: dict[str, object],
    context: str,
    strategy: ContextStrategy,
    interest: InterestAssessment,
    owner_name: str,
    other_name: str,
) -> str:
    signals_block = _format_interest_block(interest, owner_name, other_name)
    return (
        f"Estratégia de contexto: {strategy.value}\n"
        f"Título da conversa: {title}\n"
        f"Participante analisado (outra pessoa): {other_name}\n"
        f"Participante proprietário: {owner_name}\n\n"
        f"Avaliação de interesse (calculada pelo sistema — não recalcule):\n"
        f"- interest_score: {interest.interest_score}\n"
        f"- interest_level: {interest.interest_level.value}\n"
        f"- confidence_score: {interest.confidence_score}\n"
        f"- reciprocidade: {json.dumps(_reciprocity_payload(interest), ensure_ascii=False)}\n\n"
        f"Sinais classificados:\n{signals_block}\n\n"
        f"Métricas objetivas (JSON):\n{json.dumps(metrics, ensure_ascii=False, indent=2)}\n\n"
        f"Contexto resumido da conversa:\n{context}"
    )


def _build_ask_user_prompt(
    *,
    title: str,
    question: str,
    metrics: dict[str, object],
    context: str,
    existing_summary: str | None,
    strategy: ContextStrategy,
    existing_analysis: ConversationAnalysis | None,
) -> str:
    summary_block = existing_summary or "Nenhum resumo anterior disponível."
    interest_block = ""
    if existing_analysis and existing_analysis.interest_level:
        interest_block = (
            f"\nNível de interesse pré-calculado: {existing_analysis.interest_level} "
            f"(confiança {existing_analysis.confidence_score}%). "
            "Use esses valores como referência, sem afirmar certezas.\n"
        )
    return (
        f"Estratégia de contexto: {strategy.value}\n"
        f"Título da conversa: {title}\n\n"
        f"Pergunta do usuário: {question}\n\n"
        f"Resumo anterior (se existir):\n{summary_block}\n"
        f"{interest_block}\n"
        f"Métricas objetivas (JSON):\n{json.dumps(metrics, ensure_ascii=False, indent=2)}\n\n"
        f"Contexto resumido da conversa:\n{context}"
    )


def _format_interest_block(
    interest: InterestAssessment,
    owner_name: str,
    other_name: str,
) -> str:
    sections = [
        ("POSITIVOS", interest.positive_signals),
        ("NEUTROS", interest.neutral_signals),
        ("NEGATIVOS", interest.negative_signals),
    ]
    lines = [f"Análise focada em {other_name} (owner: {owner_name})"]
    for title, signals in sections:
        if not signals:
            continue
        lines.append(f"\n{title}:")
        for item in signals:
            lines.append(f"- [{item.key.value}] {item.observation} (força={item.strength:.2f})")
    return "\n".join(lines)


def _reciprocity_payload(interest: InterestAssessment) -> dict[str, object]:
    return {
        "initiation_balance": interest.reciprocity.initiation_balance,
        "message_balance": interest.reciprocity.message_balance,
        "question_balance": interest.reciprocity.question_balance,
        "overall_score": interest.reciprocity.overall_score,
        "observation": interest.reciprocity.observation,
    }


def _metrics_string_list(metrics: dict[str, object], key: str) -> list[str]:
    raw = metrics.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _stored_signals_to_read(signals: list[dict[str, object]]) -> list[SignalRead]:
    result: list[SignalRead] = []
    for item in signals:
        message_ids_raw = item.get("message_ids", [])
        if not isinstance(message_ids_raw, list) or not message_ids_raw:
            continue
        message_ids = [UUID(str(message_id)) for message_id in message_ids_raw]
        metadata = item.get("metadata", {})
        result.append(
            SignalRead(
                key=str(item.get("key", "")),
                label=str(item.get("label", "")),
                participant=str(item.get("participant", "")),
                strength=float(item.get("strength", 0)),
                observation=str(item.get("observation", "")),
                message_ids=message_ids,
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )
    return result


def _classified_to_signal_read(signals: tuple[ClassifiedSignal, ...]) -> list[SignalRead]:
    return [
        SignalRead(
            key=item.key.value,
            label=item.label,
            participant=item.participant,
            strength=item.strength,
            observation=item.observation,
            message_ids=list(item.message_ids),
            metadata=item.metadata,
        )
        for item in signals
        if item.message_ids
    ]


def _build_analyze_response(
    stored: ConversationAnalysis,
    observations: list[str],
    inferences: list[str],
    context_strategy: str,
    interest: InterestAssessment,
    evidence: list[EvidenceRead],
) -> AnalyzeResponse:
    analysis = AnalysisRead.model_validate(stored)
    return AnalyzeResponse(
        analysis=analysis,
        observations=observations,
        inferences=inferences,
        context_strategy=context_strategy,
        interest_score=interest.interest_score,
        interest_level=interest.interest_level.value,
        confidence_score=interest.confidence_score,
        positive_signals=_classified_to_signal_read(interest.positive_signals),
        neutral_signals=_classified_to_signal_read(interest.neutral_signals),
        negative_signals=_classified_to_signal_read(interest.negative_signals),
        evidence=evidence,
        reciprocity=_reciprocity_payload(interest),
    )

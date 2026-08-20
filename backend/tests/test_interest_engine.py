import re
from uuid import uuid4

import pytest

from app.interest_engine.score_calculator import (
    BASE_INTEREST_SCORE,
    MAX_SINGLE_SIGNAL_CONTRIBUTION,
    calculate_interest_score,
    contribution_breakdown,
    score_to_interest_level,
)
from app.interest_engine.signal_classifier import classify_signals
from app.interest_engine.timeline_analyzer import analyze_timeline, run_interest_analysis
from app.interest_engine.types import (
    ClassifiedSignal,
    InterestLevel,
    SignalKey,
    SignalPolarity,
)
from tests.helpers.interest_scenarios import (
    high_reciprocity_conversation,
    low_volume_conversation,
    metrics_for,
    mixed_signals_conversation,
    one_sided_conversation,
    recent_drop_conversation,
)


def _classified(
    key: SignalKey,
    *,
    strength: float = 1.0,
    message_ids: tuple | None = None,
) -> ClassifiedSignal:
    return ClassifiedSignal(
        key=key,
        label=key.value,
        polarity=SignalPolarity.POSITIVE
        if key
        in {
            SignalKey.INICIA_CONVERSAS,
            SignalKey.FAZ_PERGUNTAS,
            SignalKey.RESPONDE_ELABORADO,
        }
        else SignalPolarity.NEGATIVE,
        participant="Beatriz",
        strength=strength,
        message_ids=message_ids or (uuid4(),),
        observation=f"Sinal {key.value}",
    )


def test_high_reciprocity_scores_higher_than_one_sided() -> None:
    high_msgs, owner, other = high_reciprocity_conversation()
    one_msgs, owner2, other2 = one_sided_conversation()
    high = run_interest_analysis(
        high_msgs, metrics_for(high_msgs), owner_name=owner, other_name=other, gap_hours=4
    )
    one = run_interest_analysis(
        one_msgs, metrics_for(one_msgs), owner_name=owner2, other_name=other2, gap_hours=4
    )
    assert high.interest_score > one.interest_score
    assert high.confidence_score > one.confidence_score


def test_low_volume_caps_confidence() -> None:
    messages, owner, other = low_volume_conversation()
    assessment = run_interest_analysis(
        messages, metrics_for(messages), owner_name=owner, other_name=other, gap_hours=4
    )
    assert assessment.confidence_score <= 35
    assert len(messages) < 12


def test_mixed_signals_stays_near_moderate_band() -> None:
    messages, owner, other = mixed_signals_conversation()
    assessment = run_interest_analysis(
        messages, metrics_for(messages), owner_name=owner, other_name=other, gap_hours=4
    )
    assert 25 <= assessment.interest_score <= 75


def test_recent_drop_timeline_shows_decline() -> None:
    messages, owner, other = recent_drop_conversation()
    timeline = analyze_timeline(messages, owner_name=owner, other_name=other, gap_hours=4)
    full = next(item for item in timeline if item.key == "full")
    week = next(item for item in timeline if item.key == "7d")
    assert week.message_count < full.message_count
    assert week.interest_score <= full.interest_score


def test_single_positive_signal_cannot_dominate_score() -> None:
    baseline = calculate_interest_score([], [])
    only_initiation = calculate_interest_score(
        [_classified(SignalKey.INICIA_CONVERSAS, strength=1.0)],
        [],
    )
    delta = abs(only_initiation - baseline)
    assert delta <= MAX_SINGLE_SIGNAL_CONTRIBUTION
    assert score_to_interest_level(only_initiation) in {
        InterestLevel.BAIXO,
        InterestLevel.MODERADO,
        InterestLevel.ALTO,
    }


def test_single_negative_signal_cannot_dominate_score() -> None:
    baseline = calculate_interest_score([], [])
    only_short = calculate_interest_score(
        [],
        [_classified(SignalKey.RESPOSTAS_CURTAS, strength=1.0)],
    )
    delta = abs(baseline - only_short)
    assert delta <= MAX_SINGLE_SIGNAL_CONTRIBUTION


def test_all_signals_have_evidence_message_ids() -> None:
    messages, owner, other = high_reciprocity_conversation()
    assessment = run_interest_analysis(
        messages, metrics_for(messages), owner_name=owner, other_name=other, gap_hours=4
    )
    stored_signals = (
        list(assessment.positive_signals)
        + list(assessment.neutral_signals)
        + list(assessment.negative_signals)
    )
    assert stored_signals
    for signal in stored_signals:
        assert signal.message_ids, f"Sinal sem evidência: {signal.key}"
    for record in assessment.evidence:
        assert record.message_ids


def test_contribution_breakdown_documents_weights() -> None:
    messages, owner, other = mixed_signals_conversation()
    assessment = run_interest_analysis(
        messages, metrics_for(messages), owner_name=owner, other_name=other, gap_hours=4
    )
    breakdown = contribution_breakdown(
        list(assessment.positive_signals),
        list(assessment.negative_signals),
    )
    assert breakdown["base_score"] == BASE_INTEREST_SCORE
    assert breakdown["max_single_signal_contribution"] == MAX_SINGLE_SIGNAL_CONTRIBUTION


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (10, InterestLevel.MUITO_BAIXO),
        (35, InterestLevel.BAIXO),
        (55, InterestLevel.MODERADO),
        (75, InterestLevel.ALTO),
        (95, InterestLevel.MUITO_ALTO),
    ],
)
def test_score_to_level_boundaries(score: int, expected: InterestLevel) -> None:
    assert score_to_interest_level(score) is expected


def test_classify_preserves_polarity_from_spec() -> None:
    from app.interest_engine.signal_detector import detect_signals

    messages, owner, other = one_sided_conversation()
    metrics = metrics_for(messages)
    detected = detect_signals(messages, metrics, owner_name=owner, other_name=other)
    classified = classify_signals(detected)
    keys = {item.key for item in classified}
    assert SignalKey.RESPOSTAS_CURTAS in keys or SignalKey.FALTA_RECIPROCIDADE in keys


def test_hidden_media_does_not_trigger_text_signals() -> None:
    from datetime import UTC, datetime, timedelta

    from app.conversation.metric_message import MetricMessage
    from app.conversation.metrics import calculate_conversation_metrics
    from app.conversation.types import MessageType

    base = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    owner = "Beatriz"
    other = "Marina"

    messages = [
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=owner,
            timestamp=base,
            message_type=MessageType.TEXT,
            content="Oi",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=other,
            timestamp=base + timedelta(minutes=1),
            message_type=MessageType.MEDIA_OCULTA,
            content="<Mídia oculta>",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=other,
            timestamp=base + timedelta(minutes=2),
            message_type=MessageType.MEDIA_OCULTA,
            content="<Mídia oculta>",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=other,
            timestamp=base + timedelta(minutes=3),
            message_type=MessageType.MEDIA_OCULTA,
            content="<Mídia oculta>",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=other,
            timestamp=base + timedelta(minutes=4),
            message_type=MessageType.MEDIA_OCULTA,
            content="<Mídia oculta>",
        ),
    ]

    metrics = calculate_conversation_metrics(messages, gap_hours=4)
    assessment = run_interest_analysis(
        messages,
        metrics,
        owner_name=owner,
        other_name=other,
        gap_hours=4,
    )

    keys = {
        signal.key
        for signal in [
            *assessment.positive_signals,
            *assessment.neutral_signals,
            *assessment.negative_signals,
        ]
    }

    assert SignalKey.MANTEM_ASSUNTOS not in keys
    assert SignalKey.RETOMA_ASSUNTOS not in keys
    assert SignalKey.RESPOSTAS_CURTAS not in keys
    assert SignalKey.TAMANHO_MENSAGEM not in keys
    assert SignalKey.EVITA_ASSUNTOS not in keys


def test_hidden_media_replies_do_not_trigger_evita_assuntos() -> None:
    from datetime import UTC, datetime, timedelta

    from app.conversation.metric_message import MetricMessage
    from app.conversation.metrics import calculate_conversation_metrics
    from app.conversation.types import MessageType
    from app.interest_engine.signal_detector import detect_signals
    from app.interest_engine.signal_classifier import classify_signals

    base = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    owner = "Alle"
    other = "Giulia"

    messages = [
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=owner,
            timestamp=base,
            message_type=MessageType.TEXT,
            content="O que você achou do filme de ontem?",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=other,
            timestamp=base + timedelta(minutes=1),
            message_type=MessageType.MEDIA_OCULTA,
            content="<Mídia oculta>",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=owner,
            timestamp=base + timedelta(minutes=2),
            message_type=MessageType.TEXT,
            content="E sobre o jantar, topa sair?",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=other,
            timestamp=base + timedelta(minutes=3),
            message_type=MessageType.MEDIA_OCULTA,
            content="<Mídia oculta>",
        ),
    ]

    metrics = calculate_conversation_metrics(messages, gap_hours=4)
    detected = detect_signals(messages, metrics, owner_name=owner, other_name=other)
    classified = classify_signals(detected)
    keys = {item.key for item in classified}

    assert SignalKey.EVITA_ASSUNTOS not in keys


def test_transcribed_audio_is_eligible_for_text_content_signals() -> None:
    from datetime import UTC, datetime, timedelta

    from app.conversation.metric_message import MetricMessage
    from app.conversation.metrics import calculate_conversation_metrics
    from app.conversation.types import MessageType
    from app.interest_engine.signal_classifier import classify_signals
    from app.interest_engine.signal_detector import detect_signals

    base = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    owner = "Beatriz"
    other = "Marina"
    transcribed_text = (
        "Transcrição fictícia do áudio clip.opus com conteúdo longo o suficiente "
        "para ser considerado elaborado pelo detector de sinais do Interest Engine."
    )

    messages = [
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=owner,
            timestamp=base,
            message_type=MessageType.TEXT,
            content="Oi, me manda um áudio?",
        ),
        MetricMessage(
            id=uuid4(),
            sender_id=uuid4(),
            sender_name=other,
            timestamp=base + timedelta(minutes=1),
            message_type=MessageType.AUDIO,
            content=transcribed_text,
        ),
    ]

    metrics = calculate_conversation_metrics(messages, gap_hours=4)
    detected = detect_signals(
        messages,
        metrics,
        owner_name=owner,
        other_name=other,
        gap_hours=4,
    )
    classified = classify_signals(detected)
    keys = {item.key for item in classified}

    assert SignalKey.TAMANHO_MENSAGEM in keys
    assert SignalKey.RESPONDE_ELABORADO in keys


ABSOLUTE_LANGUAGE_PATTERN = re.compile(
    r"\b(definitivamente|com certeza|ela está interessada|ele está interessado|"
    r"não quer nada|claramente não se importa)\b",
    re.IGNORECASE,
)


@pytest.mark.asyncio
async def test_fake_llm_summary_avoids_absolute_language() -> None:
    from app.ai.llm.fake_provider import FakeLLMProvider
    from app.ai.llm.schemas import ConversationSummaryOutput

    provider = FakeLLMProvider(summary_text="Os sinais sugerem reciprocidade moderada.")
    result = await provider.generate_structured(
        system_prompt="teste",
        user_prompt="teste",
        response_model=ConversationSummaryOutput,
    )
    payload = result.data.summary + " ".join(result.data.observations + result.data.inferences)
    assert not ABSOLUTE_LANGUAGE_PATTERN.search(payload)

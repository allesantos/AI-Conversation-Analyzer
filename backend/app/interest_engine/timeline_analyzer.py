from __future__ import annotations

from datetime import UTC, timedelta
from typing import Any

from app.conversation.metric_message import MetricMessage
from app.conversation.metrics import calculate_conversation_metrics
from app.interest_engine.confidence import calculate_confidence_score
from app.interest_engine.evidence_builder import build_evidence_records
from app.interest_engine.reciprocity import analyze_reciprocity
from app.interest_engine.score_calculator import calculate_interest_score, score_to_interest_level
from app.interest_engine.signal_classifier import classify_signals, split_by_polarity
from app.interest_engine.signal_detector import detect_signals
from app.interest_engine.types import InterestAssessment, TimelinePeriod


def run_interest_analysis(
    messages: list[MetricMessage],
    metrics: dict[str, Any],
    *,
    owner_name: str,
    other_name: str,
    gap_hours: float,
) -> InterestAssessment:
    detected = detect_signals(
        messages,
        metrics,
        owner_name=owner_name,
        other_name=other_name,
        gap_hours=gap_hours,
    )
    classified = classify_signals(detected)
    positive, neutral, negative = split_by_polarity(classified)
    score = calculate_interest_score(positive, negative)
    level = score_to_interest_level(score)
    confidence = calculate_confidence_score(metrics, classified)
    reciprocity = analyze_reciprocity(metrics, owner_name=owner_name, other_name=other_name)
    evidence = build_evidence_records(classified)
    return InterestAssessment(
        interest_score=score,
        interest_level=level,
        confidence_score=confidence,
        positive_signals=tuple(positive),
        neutral_signals=tuple(neutral),
        negative_signals=tuple(negative),
        reciprocity=reciprocity,
        evidence=tuple(evidence),
    )


TIMELINE_PERIODS: tuple[tuple[str, str, int | None], ...] = (
    ("7d", "Últimos 7 dias", 7),
    ("30d", "Últimos 30 dias", 30),
    ("90d", "Últimos 90 dias", 90),
    ("full", "Histórico completo", None),
)


def analyze_timeline(
    messages: list[MetricMessage],
    *,
    owner_name: str,
    other_name: str,
    gap_hours: float,
) -> list[TimelinePeriod]:
    ordered = sorted(messages, key=lambda item: (item.timestamp, str(item.id)))
    if not ordered:
        return []

    end = ordered[-1].timestamp.astimezone(UTC)
    periods: list[TimelinePeriod] = []

    for key, label, days in TIMELINE_PERIODS:
        if days is None:
            window = ordered
        else:
            start = end - timedelta(days=days)
            window = [item for item in ordered if item.timestamp.astimezone(UTC) >= start]
        if not window:
            continue

        metrics = calculate_conversation_metrics(window, gap_hours=gap_hours)
        assessment = run_interest_analysis(
            window,
            metrics,
            owner_name=owner_name,
            other_name=other_name,
            gap_hours=gap_hours,
        )
        periods.append(
            TimelinePeriod(
                key=key,
                label=label,
                message_count=len(window),
                interest_score=assessment.interest_score,
                interest_level=assessment.interest_level,
                confidence_score=assessment.confidence_score,
                positive_count=len(assessment.positive_signals),
                neutral_count=len(assessment.neutral_signals),
                negative_count=len(assessment.negative_signals),
                summary_observation=_timeline_summary(assessment, label),
            )
        )
    return periods


def _timeline_summary(assessment: InterestAssessment, label: str) -> str:
    return (
        f"No período ({label}), os sinais sugerem nível {assessment.interest_level.value} "
        f"com confiança {assessment.confidence_score}% "
        f"({len(assessment.positive_signals)} positivos, "
        f"{len(assessment.negative_signals)} negativos)."
    )

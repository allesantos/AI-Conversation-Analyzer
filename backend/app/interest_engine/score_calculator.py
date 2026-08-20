from __future__ import annotations

from typing import Any

from app.interest_engine.types import ClassifiedSignal, InterestLevel, SignalPolarity
from app.interest_engine.weights import (
    BASE_INTEREST_SCORE,
    MAX_NEGATIVE_TOTAL_CONTRIBUTION,
    MAX_POSITIVE_TOTAL_CONTRIBUTION,
    MAX_SINGLE_SIGNAL_CONTRIBUTION,
    NEGATIVE_SIGNAL_WEIGHTS,
    POSITIVE_SIGNAL_WEIGHTS,
)


def calculate_interest_score(
    positive: list[ClassifiedSignal],
    negative: list[ClassifiedSignal],
) -> int:
    """Combina sinais com pesos nomeados; nenhum sinal domina sozinho."""
    score = float(BASE_INTEREST_SCORE)
    score += _apply_weighted_signals(
        positive,
        POSITIVE_SIGNAL_WEIGHTS,
        MAX_POSITIVE_TOTAL_CONTRIBUTION,
    )
    score -= _apply_weighted_signals(
        negative,
        NEGATIVE_SIGNAL_WEIGHTS,
        MAX_NEGATIVE_TOTAL_CONTRIBUTION,
    )
    return int(max(0, min(100, round(score))))


def score_to_interest_level(score: int) -> InterestLevel:
    if score <= 20:
        return InterestLevel.MUITO_BAIXO
    if score <= 40:
        return InterestLevel.BAIXO
    if score <= 60:
        return InterestLevel.MODERADO
    if score <= 80:
        return InterestLevel.ALTO
    return InterestLevel.MUITO_ALTO


def contribution_breakdown(
    positive: list[ClassifiedSignal],
    negative: list[ClassifiedSignal],
) -> dict[str, Any]:
    """Expõe contribuições por sinal — útil para testes e calibração."""
    return {
        "base_score": BASE_INTEREST_SCORE,
        "positive": _signal_contributions(positive, POSITIVE_SIGNAL_WEIGHTS),
        "negative": _signal_contributions(negative, NEGATIVE_SIGNAL_WEIGHTS),
        "max_single_signal_contribution": MAX_SINGLE_SIGNAL_CONTRIBUTION,
    }


def _apply_weighted_signals(
    signals: list[ClassifiedSignal],
    weights: dict,
    total_cap: float,
) -> float:
    raw_contributions: list[float] = []
    for item in signals:
        weight = weights.get(item.key, 0.0)
        if weight <= 0:
            continue
        contribution = min(
            MAX_SINGLE_SIGNAL_CONTRIBUTION,
            weight * item.strength * 100,
        )
        raw_contributions.append(contribution)

    if not raw_contributions:
        return 0.0

    total = sum(raw_contributions)
    if total <= total_cap:
        return total
    scale = total_cap / total
    return sum(value * scale for value in raw_contributions)


def _signal_contributions(signals: list[ClassifiedSignal], weights: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in signals:
        weight = weights.get(item.key, 0.0)
        if weight <= 0 and item.polarity is not SignalPolarity.NEUTRAL:
            continue
        rows.append(
            {
                "key": item.key.value,
                "strength": item.strength,
                "weight": weight,
                "contribution": round(
                    min(MAX_SINGLE_SIGNAL_CONTRIBUTION, weight * item.strength * 100),
                    2,
                ),
            }
        )
    return rows

from __future__ import annotations

from app.interest_engine.types import (
    SIGNAL_LABELS,
    SIGNAL_POLARITY,
    ClassifiedSignal,
    DetectedSignal,
    SignalPolarity,
)


def classify_signals(detected: list[DetectedSignal]) -> list[ClassifiedSignal]:
    classified: list[ClassifiedSignal] = []
    for item in detected:
        polarity = SIGNAL_POLARITY[item.key]
        classified.append(
            ClassifiedSignal(
                key=item.key,
                label=SIGNAL_LABELS[item.key],
                polarity=polarity,
                participant=item.participant,
                strength=max(0.0, min(1.0, item.strength)),
                message_ids=item.message_ids,
                observation=item.observation,
                metadata=item.metadata,
            )
        )
    return classified


def split_by_polarity(
    signals: list[ClassifiedSignal],
) -> tuple[list[ClassifiedSignal], list[ClassifiedSignal], list[ClassifiedSignal]]:
    positive = [item for item in signals if item.polarity is SignalPolarity.POSITIVE]
    neutral = [item for item in signals if item.polarity is SignalPolarity.NEUTRAL]
    negative = [item for item in signals if item.polarity is SignalPolarity.NEGATIVE]
    return positive, neutral, negative

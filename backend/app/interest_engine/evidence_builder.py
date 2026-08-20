from __future__ import annotations

from typing import Any

from app.interest_engine.types import ClassifiedSignal, EvidenceRecord


def build_evidence_records(signals: list[ClassifiedSignal]) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    for item in signals:
        if not item.message_ids:
            continue
        records.append(
            EvidenceRecord(
                signal_key=item.key,
                signal_label=item.label,
                polarity=item.polarity,
                message_ids=item.message_ids,
                observation=item.observation,
            )
        )
    return records


def signals_for_storage(signals: list[ClassifiedSignal]) -> list[dict[str, Any]]:
    return [
        {
            "key": item.key.value,
            "label": item.label,
            "participant": item.participant,
            "strength": round(item.strength, 3),
            "observation": item.observation,
            "message_ids": [str(message_id) for message_id in item.message_ids],
            "metadata": item.metadata,
        }
        for item in signals
        if item.message_ids
    ]

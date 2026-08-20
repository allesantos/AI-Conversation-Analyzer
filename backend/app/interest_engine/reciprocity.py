from __future__ import annotations

from typing import Any

from app.interest_engine.types import ReciprocityAnalysis


def analyze_reciprocity(
    metrics: dict[str, Any],
    *,
    owner_name: str,
    other_name: str,
) -> ReciprocityAnalysis:
    initiations: dict[str, int] = metrics.get("conversation_initiations", {})
    messages_by: dict[str, int] = metrics.get("messages_by_participant", {})
    questions_by: dict[str, int] = metrics.get("questions_by_participant", {})

    other_starts = initiations.get(other_name, 0)
    owner_starts = initiations.get(owner_name, 0)
    initiation_balance = _balance_ratio(other_starts, owner_starts)

    other_msgs = messages_by.get(other_name, 0)
    owner_msgs = messages_by.get(owner_name, 0)
    message_balance = _balance_ratio(other_msgs, owner_msgs)

    other_q = questions_by.get(other_name, 0)
    owner_q = questions_by.get(owner_name, 0)
    question_balance = _balance_ratio(other_q, owner_q)

    overall = round((initiation_balance + message_balance + question_balance) / 3, 3)
    observation = (
        f"Reciprocidade: iniciativas {other_starts}/{owner_starts}, "
        f"mensagens {other_msgs}/{owner_msgs}, perguntas {other_q}/{owner_q}."
    )
    return ReciprocityAnalysis(
        initiation_balance=initiation_balance,
        message_balance=message_balance,
        question_balance=question_balance,
        overall_score=overall,
        observation=observation,
        metadata={
            "other_name": other_name,
            "owner_name": owner_name,
        },
    )


def _balance_ratio(left: int, right: int) -> float:
    total = left + right
    if total == 0:
        return 0.5
    share = left / total
    return round(1 - abs(share - 0.5) * 2, 3)

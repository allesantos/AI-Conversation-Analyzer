from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.conversation.metric_message import MetricMessage
from app.conversation.metrics import calculate_conversation_metrics
from app.conversation.types import MessageType


def _msg(
    *,
    sender: str,
    content: str,
    timestamp: datetime,
    message_type: MessageType = MessageType.TEXT,
) -> MetricMessage:
    return MetricMessage(
        id=uuid4(),
        sender_id=uuid4(),
        sender_name=sender,
        timestamp=timestamp,
        message_type=message_type,
        content=content,
    )


def high_reciprocity_conversation() -> tuple[list[MetricMessage], str, str]:
    """Reciprocidade alta: ambos iniciam, perguntam e respondem elaborado."""
    owner, other = "Alex", "Beatriz"
    base = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    messages: list[MetricMessage] = []
    for index in range(40):
        sender = other if index % 2 == 0 else owner
        gap = timedelta(hours=5 if index % 8 == 0 else 0, minutes=index * 12)
        content = (
            f"Olá, vamos conversar sobre viagem e cinema? Tenho várias ideias legais {index}."
            if index % 3
            else f"Adorei o assunto! Me conta mais sobre o plano de sábado? {index}?"
        )
        messages.append(_msg(sender=sender, content=content, timestamp=base + gap))
    return messages, owner, other


def one_sided_conversation() -> tuple[list[MetricMessage], str, str]:
    """Só o owner inicia/pergunta; other responde curto."""
    owner, other = "Alex", "Beatriz"
    base = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
    messages: list[MetricMessage] = []
    for index in range(24):
        if index % 2 == 0:
            content = f"E aí, bora marcar um café amanhã? Como você está? {index}?"
            sender = owner
        else:
            content = "ok"
            sender = other
        messages.append(
            _msg(sender=sender, content=content, timestamp=base + timedelta(hours=index * 5))
        )
    return messages, owner, other


def low_volume_conversation() -> tuple[list[MetricMessage], str, str]:
    """Poucas mensagens — confiança deve permanecer baixa."""
    owner, other = "Alex", "Beatriz"
    base = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    messages = [
        _msg(
            sender=other,
            content="Oi! Vi aquele filme e lembrei de você, o que achou do final?",
            timestamp=base,
        ),
        _msg(sender=owner, content="Foi ótimo!", timestamp=base + timedelta(minutes=5)),
        _msg(
            sender=other,
            content="Vamos marcar cinema sábado?",
            timestamp=base + timedelta(minutes=10),
        ),
    ]
    return messages, owner, other


def mixed_signals_conversation() -> tuple[list[MetricMessage], str, str]:
    """Sinais positivos e negativos concorrendo."""
    owner, other = "Alex", "Beatriz"
    base = datetime(2026, 4, 1, 8, 0, tzinfo=UTC)
    messages: list[MetricMessage] = []
    for index in range(20):
        sender = other if index % 4 == 0 else owner
        if sender == other and index % 8 == 0:
            content = "Vamos jantar sábado? Adorei nossa conversa sobre viagem!"
        elif sender == other:
            content = "sim"
        else:
            content = f"Como foi seu dia? Queria saber da viagem {index}?"
        messages.append(
            _msg(sender=sender, content=content, timestamp=base + timedelta(hours=index * 6))
        )
    return messages, owner, other


def recent_drop_conversation() -> tuple[list[MetricMessage], str, str]:
    """Atividade forte no início e queda nas últimas semanas."""
    owner, other = "Alex", "Beatriz"
    base = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    messages: list[MetricMessage] = []
    for index in range(30):
        sender = other if index % 2 == 0 else owner
        content = f"Troca ativa sobre planos e viagem {index}?" if index < 20 else "ok"
        messages.append(
            _msg(sender=sender, content=content, timestamp=base + timedelta(days=index))
        )
    # gap de ~20 dias e uma resposta curta recente
    messages.append(
        _msg(
            sender=other,
            content="ocupada",
            timestamp=base + timedelta(days=52),
        )
    )
    return messages, owner, other


def metrics_for(messages: list[MetricMessage]) -> dict:
    return calculate_conversation_metrics(messages, gap_hours=4)


def message_ids(messages: list[MetricMessage]) -> list[UUID]:
    return [item.id for item in messages]

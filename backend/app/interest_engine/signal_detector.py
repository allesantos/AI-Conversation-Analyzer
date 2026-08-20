from __future__ import annotations

import re
import statistics
from datetime import timedelta
from typing import Any
from uuid import UUID

from app.conversation.metric_message import MetricMessage
from app.conversation.metrics import DEFAULT_GAP_HOURS
from app.conversation.types import MessageType
from app.interest_engine.types import DetectedSignal, SignalKey
from app.interest_engine.weights import (
    ELABORATE_MESSAGE_CHARS,
    EMOJI_PATTERN_CHARS,
    INITIATION_IMBALANCE_RATIO,
    MIN_TOPIC_OVERLAP_TOKENS,
    QUESTION_IGNORE_MIN_LENGTH,
    SHORT_MESSAGE_CHARS,
    SPONTANEOUS_SHARE_CHARS,
)

_PLAN_ACCEPT_PATTERN = re.compile(
    r"\b(vamos|bora|marcar|encontro|sábado|sabado|domingo|amanhã|amanha|café|cafe|jantar|combinar)\b",
    re.IGNORECASE,
)
_PLAN_REFUSAL_PATTERN = re.compile(
    r"\b(não posso|nao posso|não dá|nao da|sem chance|não vou poder|nao vou poder|"
    r"esse dia não|esse dia nao)\b",
    re.IGNORECASE,
)
_DISINTEREST_PATTERN = re.compile(
    r"\b(não tenho interesse|nao tenho interesse|sem interesse|não quero|nao quero|"
    r"deixa pra lá|deixa pra la|não rola|nao rola)\b",
    re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"[a-zà-ú0-9]{4,}", re.IGNORECASE)

_HIDDEN_MEDIA_PLACEHOLDERS = frozenset(
    {
        "<mídia oculta>",
        "<midia oculta>",
        "áudio enviado pelo usuário",
        "audio enviado pelo usuario",
    }
)


def detect_signals(
    messages: list[MetricMessage],
    metrics: dict[str, Any],
    *,
    owner_name: str,
    other_name: str,
    gap_hours: float = DEFAULT_GAP_HOURS,
) -> list[DetectedSignal]:
    """Identifica sinais brutos a partir de métricas (Fase 3) + heurísticas sobre mensagens."""
    ordered = sorted(messages, key=lambda item: (item.timestamp, str(item.id)))
    analyzable = [
        item
        for item in ordered
        if item.message_type not in {MessageType.SYSTEM, MessageType.MEDIA_OCULTA}
    ]
    owner_msgs = [item for item in analyzable if item.sender_name == owner_name]
    other_msgs = [item for item in analyzable if item.sender_name == other_name]
    if not other_msgs:
        return []

    signals: list[DetectedSignal] = []
    signals.extend(_detect_initiation_signals(metrics, other_name, other_msgs, owner_name))
    signals.extend(_detect_question_signals(metrics, other_name, other_msgs))
    signals.extend(_detect_length_signals(other_msgs, other_name))
    signals.extend(_detect_topic_signals(other_msgs, other_name, gap_hours))
    signals.extend(_detect_sharing_signals(other_msgs, owner_msgs, other_name))
    signals.extend(_detect_plan_signals(other_msgs, other_name))
    signals.extend(_detect_audio_signals(other_msgs, owner_msgs, other_name))
    signals.extend(_detect_continuity_signals(other_msgs, other_name, gap_hours))
    signals.extend(_detect_reciprocity_signal(metrics, owner_name, other_name, other_msgs))
    signals.extend(_detect_neutral_signals(metrics, other_msgs, other_name, gap_hours))
    signals.extend(_detect_negative_interaction_signals(owner_msgs, other_msgs, other_name))
    signals.extend(_detect_explicit_negative_signals(other_msgs, other_name))
    return [item for item in signals if item.message_ids]


def _detect_initiation_signals(
    metrics: dict[str, Any],
    other_name: str,
    other_msgs: list[MetricMessage],
    owner_name: str,
) -> list[DetectedSignal]:
    initiations: dict[str, int] = metrics.get("conversation_initiations", {})
    other_starts = initiations.get(other_name, 0)
    owner_starts = initiations.get(owner_name, 0)
    total_starts = other_starts + owner_starts
    if other_starts <= 0:
        return []

    strength = min(1.0, other_starts / max(total_starts, 1))
    gap = timedelta(hours=float(metrics.get("settings", {}).get("conversation_gap_hours", 4)))
    start_ids: list = []
    previous = None
    for item in other_msgs:
        if previous is None or item.timestamp - previous.timestamp > gap:
            start_ids.append(item.id)
        previous = item

    return [
        DetectedSignal(
            key=SignalKey.INICIA_CONVERSAS,
            participant=other_name,
            strength=strength,
            message_ids=tuple(start_ids[:10]),
            observation=(
                f"{other_name} iniciou {other_starts} conversa(s) no período analisado "
                f"(sinal de iniciativa, não de reciprocidade)."
            ),
            metadata={"count": other_starts, "owner_starts": owner_starts},
        )
    ]


def _detect_question_signals(
    metrics: dict[str, Any],
    other_name: str,
    other_msgs: list[MetricMessage],
) -> list[DetectedSignal]:
    counts: dict[str, int] = metrics.get("questions_by_participant", {})
    count = counts.get(other_name, 0)
    if count <= 0:
        return []
    question_msgs = [item for item in other_msgs if item.content.strip().endswith("?")]
    strength = min(1.0, count / max(len(other_msgs), 1) * 4)
    return [
        DetectedSignal(
            key=SignalKey.FAZ_PERGUNTAS,
            participant=other_name,
            strength=max(0.3, strength),
            message_ids=tuple(item.id for item in question_msgs[:8]),
            observation=f"{other_name} fez {count} pergunta(s) identificável(is).",
            metadata={"count": count},
        )
    ]


def _detect_length_signals(
    other_msgs: list[MetricMessage], other_name: str
) -> list[DetectedSignal]:
    signals: list[DetectedSignal] = []
    text_msgs = [item for item in other_msgs if item.message_type != MessageType.MEDIA_OCULTA]
    lengths = [len(item.content.strip()) for item in text_msgs if item.content.strip()]
    if not lengths:
        return signals

    avg_len = statistics.mean(lengths)
    short_msgs = [item for item in text_msgs if len(item.content.strip()) <= SHORT_MESSAGE_CHARS]
    elaborate_msgs = [
        item for item in text_msgs if len(item.content.strip()) >= ELABORATE_MESSAGE_CHARS
    ]
    objective_msgs = [
        item
        for item in text_msgs
        if SHORT_MESSAGE_CHARS < len(item.content.strip()) < ELABORATE_MESSAGE_CHARS
    ]

    if elaborate_msgs:
        ratio = len(elaborate_msgs) / len(text_msgs)
        signals.append(
            DetectedSignal(
                key=SignalKey.RESPONDE_ELABORADO,
                participant=other_name,
                strength=min(1.0, ratio * 2),
                message_ids=tuple(item.id for item in elaborate_msgs[:8]),
                observation=(
                    f"{other_name} enviou {len(elaborate_msgs)} mensagem(ns) elaborada(s) "
                    f"(≥{ELABORATE_MESSAGE_CHARS} caracteres)."
                ),
                metadata={"count": len(elaborate_msgs), "average_length": round(avg_len, 2)},
            )
        )

    short_ratio = len(short_msgs) / len(text_msgs)
    if short_ratio >= 0.45 and len(short_msgs) >= 3:
        signals.append(
            DetectedSignal(
                key=SignalKey.RESPOSTAS_CURTAS,
                participant=other_name,
                strength=min(1.0, short_ratio * 1.5),
                message_ids=tuple(item.id for item in short_msgs[:8]),
                observation=(
                    f"{other_name} respondeu de forma curta em {len(short_msgs)} mensagem(ns) "
                    f"de {len(text_msgs)} mensagens suas ({round(short_ratio * 100)}%)."
                ),
                metadata={"count": len(short_msgs), "ratio": round(short_ratio, 3)},
            )
        )

    if objective_msgs:
        ratio = len(objective_msgs) / len(text_msgs)
        if ratio >= 0.25:
            signals.append(
                DetectedSignal(
                    key=SignalKey.RESPOSTAS_OBJETIVAS,
                    participant=other_name,
                    strength=min(1.0, ratio),
                    message_ids=tuple(item.id for item in objective_msgs[:6]),
                    observation=f"{other_name} manteve respostas objetivas em parte das trocas.",
                    metadata={"count": len(objective_msgs)},
                )
            )

    avg_label = round(avg_len, 1)
    signals.append(
        DetectedSignal(
            key=SignalKey.TAMANHO_MENSAGEM,
            participant=other_name,
            strength=0.5,
            message_ids=tuple(item.id for item in text_msgs[:3]),
            observation=f"Média de tamanho das mensagens de {other_name}: {avg_label} chars.",
            metadata={"average_length": round(avg_len, 2)},
        )
    )
    return signals


def _detect_topic_signals(
    other_msgs: list[MetricMessage],
    other_name: str,
    gap_hours: float,
) -> list[DetectedSignal]:
    text_msgs = [item for item in other_msgs if item.message_type != MessageType.MEDIA_OCULTA]
    signals: list[DetectedSignal] = []
    maintain_ids: list = []
    resume_ids: list = []
    earlier_tokens: set[str] = set()

    for index, item in enumerate(text_msgs):
        tokens = _tokens(item.content)
        if index > 0:
            prev_tokens = _tokens(text_msgs[index - 1].content)
            overlap = tokens & prev_tokens
            if len(overlap) >= MIN_TOPIC_OVERLAP_TOKENS:
                maintain_ids.append(item.id)
        if earlier_tokens and len(tokens & earlier_tokens) >= MIN_TOPIC_OVERLAP_TOKENS:
            resume_ids.append(item.id)
        earlier_tokens |= tokens

    if maintain_ids:
        ratio = len(maintain_ids) / len(text_msgs)
        signals.append(
            DetectedSignal(
                key=SignalKey.MANTEM_ASSUNTOS,
                participant=other_name,
                strength=min(1.0, ratio * 2.5),
                message_ids=tuple(maintain_ids[:8]),
                observation=f"{other_name} manteve continuidade temática em várias mensagens.",
                metadata={"count": len(maintain_ids)},
            )
        )

    if resume_ids:
        signals.append(
            DetectedSignal(
                key=SignalKey.RETOMA_ASSUNTOS,
                participant=other_name,
                strength=min(1.0, len(resume_ids) / max(len(text_msgs), 1) * 3),
                message_ids=tuple(resume_ids[:8]),
                observation=f"{other_name} retomou assuntos mencionados anteriormente.",
                metadata={"count": len(resume_ids), "gap_hours": gap_hours},
            )
        )
    return signals


def _detect_sharing_signals(
    other_msgs: list[MetricMessage],
    owner_msgs: list[MetricMessage],
    other_name: str,
) -> list[DetectedSignal]:
    owner_question_times = {
        item.timestamp
        for item in owner_msgs
        if item.message_type != MessageType.MEDIA_OCULTA and item.content.strip().endswith("?")
    }
    shared: list[MetricMessage] = []
    for item in other_msgs:
        if item.message_type == MessageType.MEDIA_OCULTA:
            continue
        if len(item.content.strip()) < SPONTANEOUS_SHARE_CHARS:
            continue
        preceded_by_question = any(
            abs((item.timestamp - ts).total_seconds()) < 300 for ts in owner_question_times
        )
        if not preceded_by_question:
            shared.append(item)
    if not shared:
        return []
    return [
        DetectedSignal(
            key=SignalKey.COMPARTILHA_INFORMACAO,
            participant=other_name,
            strength=min(1.0, len(shared) / max(len(other_msgs), 1) * 2.5),
            message_ids=tuple(item.id for item in shared[:6]),
            observation=f"{other_name} compartilhou informações extensas sem pergunta imediata.",
            metadata={"count": len(shared)},
        )
    ]


def _detect_plan_signals(other_msgs: list[MetricMessage], other_name: str) -> list[DetectedSignal]:
    plan_msgs = [item for item in other_msgs if _PLAN_ACCEPT_PATTERN.search(item.content)]
    if not plan_msgs:
        return []
    return [
        DetectedSignal(
            key=SignalKey.PROPOE_ACEITA_PLANOS,
            participant=other_name,
            strength=min(1.0, len(plan_msgs) / max(len(other_msgs), 1) * 4),
            message_ids=tuple(item.id for item in plan_msgs[:6]),
            observation=f"{other_name} propôs/aceitou planos em {len(plan_msgs)} mensagem(ns).",
            metadata={"count": len(plan_msgs)},
        )
    ]


def _detect_audio_signals(
    other_msgs: list[MetricMessage],
    owner_msgs: list[MetricMessage],
    other_name: str,
) -> list[DetectedSignal]:
    audio_msgs = [item for item in other_msgs if item.message_type == MessageType.AUDIO]
    if not audio_msgs:
        return []
    owner_question_times = {item.timestamp for item in owner_msgs if "?" in item.content}
    spontaneous = [
        item
        for item in audio_msgs
        if not any(abs((item.timestamp - ts).total_seconds()) < 300 for ts in owner_question_times)
    ]
    target = spontaneous or audio_msgs
    return [
        DetectedSignal(
            key=SignalKey.ENVIA_AUDIO_ESPONTANEO,
            participant=other_name,
            strength=min(1.0, len(target) / max(len(other_msgs), 1) * 5),
            message_ids=tuple(item.id for item in target[:6]),
            observation=f"{other_name} enviou {len(target)} áudio(s) espontaneamente.",
            metadata={"count": len(target), "total_audio": len(audio_msgs)},
        )
    ]


def _detect_continuity_signals(
    other_msgs: list[MetricMessage],
    other_name: str,
    gap_hours: float,
) -> list[DetectedSignal]:
    if len(other_msgs) < 3:
        return []
    gaps = [
        (other_msgs[index].timestamp - other_msgs[index - 1].timestamp).total_seconds() / 3600
        for index in range(1, len(other_msgs))
    ]
    avg_gap = statistics.mean(gaps) if gaps else 0
    if avg_gap > gap_hours * 2:
        return []
    return [
        DetectedSignal(
            key=SignalKey.MANTEM_CONTINUIDADE,
            participant=other_name,
            strength=min(1.0, len(other_msgs) / 20),
            message_ids=tuple(item.id for item in other_msgs[-5:]),
            observation=f"{other_name} manteve continuidade (intervalo médio ~{avg_gap:.1f}h).",
            metadata={"average_gap_hours": round(avg_gap, 2)},
        )
    ]


def _detect_reciprocity_signal(
    metrics: dict[str, Any],
    owner_name: str,
    other_name: str,
    other_msgs: list[MetricMessage],
) -> list[DetectedSignal]:
    initiations: dict[str, int] = metrics.get("conversation_initiations", {})
    other_starts = initiations.get(other_name, 0)
    owner_starts = initiations.get(owner_name, 0)
    total = other_starts + owner_starts
    if total < 2:
        return []

    gap = timedelta(hours=float(metrics.get("settings", {}).get("conversation_gap_hours", 4)))
    start_ids: list = []
    previous = None
    for item in other_msgs:
        if previous is None or item.timestamp - previous.timestamp > gap:
            start_ids.append(item.id)
        previous = item

    other_share = other_starts / total
    if other_share >= INITIATION_IMBALANCE_RATIO and other_share <= (
        1 - INITIATION_IMBALANCE_RATIO
    ):
        return [
            DetectedSignal(
                key=SignalKey.RECIPROCIDADE_INICIATIVA,
                participant=other_name,
                strength=min(1.0, 1 - abs(other_share - 0.5) * 2),
                message_ids=tuple(start_ids[:6]),
                observation=(
                    f"Iniciativas equilibradas: {other_name} {other_starts}x, "
                    f"{owner_name} {owner_starts}x."
                ),
                metadata={"other_starts": other_starts, "owner_starts": owner_starts},
            )
        ]

    if other_share < INITIATION_IMBALANCE_RATIO:
        return [
            DetectedSignal(
                key=SignalKey.FALTA_RECIPROCIDADE,
                participant=other_name,
                strength=min(1.0, (0.5 - other_share) * 2),
                message_ids=tuple(start_ids[:6])
                if start_ids
                else tuple(item.id for item in other_msgs[:3]),
                observation=(
                    f"Comparado a {owner_name}, {other_name} iniciou proporcionalmente pouco: "
                    f"{other_starts} de {total} conversa(s) ({round(other_share * 100)}%)."
                ),
                metadata={"other_starts": other_starts, "owner_starts": owner_starts},
            )
        ]
    return []


def _detect_neutral_signals(
    metrics: dict[str, Any],
    other_msgs: list[MetricMessage],
    other_name: str,
    gap_hours: float,
) -> list[DetectedSignal]:
    signals: list[DetectedSignal] = []
    response = metrics.get("response_time_seconds", {})
    if response.get("average") is not None:
        signals.append(
            DetectedSignal(
                key=SignalKey.TEMPO_RESPOSTA,
                participant=other_name,
                strength=0.5,
                message_ids=tuple(item.id for item in other_msgs[:2]),
                observation=(
                    f"Tempo médio de resposta na conversa: {response['average']}s "
                    f"(amostra global de {response.get('count', 0)} trocas)."
                ),
                metadata=dict(response),
            )
        )

    emoji_msgs = [
        item for item in other_msgs if any(char in item.content for char in EMOJI_PATTERN_CHARS)
    ]
    if emoji_msgs:
        signals.append(
            DetectedSignal(
                key=SignalKey.EMOJIS,
                participant=other_name,
                strength=min(1.0, len(emoji_msgs) / max(len(other_msgs), 1) * 3),
                message_ids=tuple(item.id for item in emoji_msgs[:6]),
                observation=f"{other_name} usou emojis em {len(emoji_msgs)} mensagem(ns).",
                metadata={"count": len(emoji_msgs)},
            )
        )

    per_day: dict[str, int] = metrics.get("frequency", {}).get("messages_per_day", {})
    if len(per_day) >= 3:
        days = sorted(per_day.keys())
        max_gap_days = 0
        for index in range(1, len(days)):
            from datetime import date

            previous = date.fromisoformat(days[index - 1])
            current = date.fromisoformat(days[index])
            max_gap_days = max(max_gap_days, (current - previous).days)
        if max_gap_days >= 3:
            signals.append(
                DetectedSignal(
                    key=SignalKey.PERIODOS_SEM_CONVERSAR,
                    participant=other_name,
                    strength=min(1.0, max_gap_days / 7),
                    message_ids=tuple(item.id for item in other_msgs[:2]),
                    observation=f"Houve intervalo de até {max_gap_days} dia(s) sem mensagens.",
                    metadata={"max_gap_days": max_gap_days, "gap_hours": gap_hours},
                )
            )
    return signals


def _detect_negative_interaction_signals(
    owner_msgs: list[MetricMessage],
    other_msgs: list[MetricMessage],
    other_name: str,
) -> list[DetectedSignal]:
    signals: list[DetectedSignal] = []
    ignored: list[MetricMessage] = []
    avoided: list[MetricMessage] = []

    other_by_time = sorted(other_msgs, key=lambda item: item.timestamp)
    for owner_msg in owner_msgs:
        if not owner_msg.content.strip().endswith("?"):
            continue
        if len(owner_msg.content.strip()) < QUESTION_IGNORE_MIN_LENGTH:
            continue
        replies = [
            item
            for item in other_by_time
            if item.timestamp > owner_msg.timestamp
            and (item.timestamp - owner_msg.timestamp).total_seconds() < 3600 * 6
        ]
        if not replies:
            continue
        first_reply = replies[0]
        if _is_non_analyzable_reply(first_reply):
            continue
        reply_text = first_reply.content.strip().lower()
        if len(reply_text) <= SHORT_MESSAGE_CHARS or reply_text in {
            "ok",
            "sim",
            "não",
            "nao",
            "talvez",
        }:
            ignored.append(first_reply)
        owner_tokens = _tokens(owner_msg.content)
        reply_tokens = _tokens(first_reply.content)
        if owner_tokens and len(owner_tokens & reply_tokens) == 0 and len(reply_text) < 40:
            avoided.append(first_reply)

    if len(ignored) >= 2:
        signals.append(
            DetectedSignal(
                key=SignalKey.IGNORA_PERGUNTAS,
                participant=other_name,
                strength=min(1.0, len(ignored) / 5),
                message_ids=_unique_message_ids(ignored, 8),
                observation=f"{other_name} respondeu de forma evasiva ({len(ignored)}x).",
                metadata={"count": len(ignored)},
            )
        )

    if len(avoided) >= 2:
        signals.append(
            DetectedSignal(
                key=SignalKey.EVITA_ASSUNTOS,
                participant=other_name,
                strength=min(1.0, len(avoided) / 5),
                message_ids=_unique_message_ids(avoided, 8),
                observation=f"{other_name} desviou de assuntos ({len(avoided)} resposta(s)).",
                metadata={"count": len(ignored)},
            )
        )
    return signals


def _detect_explicit_negative_signals(
    other_msgs: list[MetricMessage],
    other_name: str,
) -> list[DetectedSignal]:
    signals: list[DetectedSignal] = []
    refusal_msgs = [item for item in other_msgs if _PLAN_REFUSAL_PATTERN.search(item.content)]
    disinterest_msgs = [item for item in other_msgs if _DISINTEREST_PATTERN.search(item.content)]

    if refusal_msgs:
        no_alt = [item for item in refusal_msgs if not _PLAN_ACCEPT_PATTERN.search(item.content)]
        target = no_alt or refusal_msgs
        signals.append(
            DetectedSignal(
                key=SignalKey.RECUSA_ENCONTROS,
                participant=other_name,
                strength=min(1.0, len(target) / 3),
                message_ids=tuple(item.id for item in target[:6]),
                observation=f"{other_name} recusou encontros/planos em {len(target)} mensagem(ns).",
                metadata={"count": len(target)},
            )
        )

    if disinterest_msgs:
        signals.append(
            DetectedSignal(
                key=SignalKey.FALTA_INTERESSE_EXPLICITA,
                participant=other_name,
                strength=min(1.0, len(disinterest_msgs) / 2),
                message_ids=tuple(item.id for item in disinterest_msgs[:6]),
                observation=f"{other_name} expressou falta de interesse explicitamente.",
                metadata={"count": len(disinterest_msgs)},
            )
        )
    return signals


def _is_non_analyzable_reply(message: MetricMessage) -> bool:
    if message.message_type in {MessageType.MEDIA_OCULTA, MessageType.SYSTEM, MessageType.IMAGE}:
        return True
    normalized = message.content.strip().lower()
    return normalized in _HIDDEN_MEDIA_PLACEHOLDERS


def _unique_message_ids(messages: list[MetricMessage], limit: int) -> tuple[UUID, ...]:
    seen: set[UUID] = set()
    ordered: list[UUID] = []
    for item in messages:
        if item.id in seen:
            continue
        seen.add(item.id)
        ordered.append(item.id)
        if len(ordered) >= limit:
            break
    return tuple(ordered)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))

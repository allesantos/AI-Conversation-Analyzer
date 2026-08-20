from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class SignalPolarity(StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class InterestLevel(StrEnum):
    MUITO_BAIXO = "MUITO_BAIXO"
    BAIXO = "BAIXO"
    MODERADO = "MODERADO"
    ALTO = "ALTO"
    MUITO_ALTO = "MUITO_ALTO"


class SignalKey(StrEnum):
    INICIA_CONVERSAS = "inicia_conversas"
    FAZ_PERGUNTAS = "faz_perguntas"
    MANTEM_ASSUNTOS = "mantem_assuntos"
    RESPONDE_ELABORADO = "responde_elaborado"
    RETOMA_ASSUNTOS = "retoma_assuntos"
    COMPARTILHA_INFORMACAO = "compartilha_informacao"
    RECIPROCIDADE_INICIATIVA = "reciprocidade_iniciativa"
    PROPOE_ACEITA_PLANOS = "propoe_aceita_planos"
    MANTEM_CONTINUIDADE = "mantem_continuidade"
    ENVIA_AUDIO_ESPONTANEO = "envia_audio_espontaneo"
    TEMPO_RESPOSTA = "tempo_resposta"
    TAMANHO_MENSAGEM = "tamanho_mensagem"
    EMOJIS = "emojis"
    RESPOSTAS_OBJETIVAS = "respostas_objetivas"
    PERIODOS_SEM_CONVERSAR = "periodos_sem_conversar"
    RESPOSTAS_CURTAS = "respostas_curtas"
    FALTA_RECIPROCIDADE = "falta_reciprocidade"
    IGNORA_PERGUNTAS = "ignora_perguntas"
    EVITA_ASSUNTOS = "evita_assuntos"
    RECUSA_ENCONTROS = "recusa_encontros"
    FALTA_INTERESSE_EXPLICITA = "falta_interesse_explicita"


SIGNAL_LABELS: dict[SignalKey, str] = {
    SignalKey.INICIA_CONVERSAS: "Inicia conversas",
    SignalKey.FAZ_PERGUNTAS: "Faz perguntas",
    SignalKey.MANTEM_ASSUNTOS: "Mantém assuntos",
    SignalKey.RESPONDE_ELABORADO: "Responde de forma elaborada",
    SignalKey.RETOMA_ASSUNTOS: "Retoma assuntos anteriores",
    SignalKey.COMPARTILHA_INFORMACAO: "Compartilha informação espontaneamente",
    SignalKey.RECIPROCIDADE_INICIATIVA: "Reciprocidade de iniciativa",
    SignalKey.PROPOE_ACEITA_PLANOS: "Propõe ou aceita planos",
    SignalKey.MANTEM_CONTINUIDADE: "Mantém continuidade",
    SignalKey.ENVIA_AUDIO_ESPONTANEO: "Envia áudio espontaneamente",
    SignalKey.TEMPO_RESPOSTA: "Tempo de resposta",
    SignalKey.TAMANHO_MENSAGEM: "Tamanho da mensagem",
    SignalKey.EMOJIS: "Uso de emojis",
    SignalKey.RESPOSTAS_OBJETIVAS: "Respostas objetivas",
    SignalKey.PERIODOS_SEM_CONVERSAR: "Períodos sem conversar",
    SignalKey.RESPOSTAS_CURTAS: "Respostas consistentemente curtas",
    SignalKey.FALTA_RECIPROCIDADE: "Falta de reciprocidade",
    SignalKey.IGNORA_PERGUNTAS: "Ignora perguntas repetidamente",
    SignalKey.EVITA_ASSUNTOS: "Evita assuntos",
    SignalKey.RECUSA_ENCONTROS: "Recusa encontros sem alternativa",
    SignalKey.FALTA_INTERESSE_EXPLICITA: "Demonstra falta de interesse explicitamente",
}

SIGNAL_POLARITY: dict[SignalKey, SignalPolarity] = {
    SignalKey.INICIA_CONVERSAS: SignalPolarity.POSITIVE,
    SignalKey.FAZ_PERGUNTAS: SignalPolarity.POSITIVE,
    SignalKey.MANTEM_ASSUNTOS: SignalPolarity.POSITIVE,
    SignalKey.RESPONDE_ELABORADO: SignalPolarity.POSITIVE,
    SignalKey.RETOMA_ASSUNTOS: SignalPolarity.POSITIVE,
    SignalKey.COMPARTILHA_INFORMACAO: SignalPolarity.POSITIVE,
    SignalKey.RECIPROCIDADE_INICIATIVA: SignalPolarity.POSITIVE,
    SignalKey.PROPOE_ACEITA_PLANOS: SignalPolarity.POSITIVE,
    SignalKey.MANTEM_CONTINUIDADE: SignalPolarity.POSITIVE,
    SignalKey.ENVIA_AUDIO_ESPONTANEO: SignalPolarity.POSITIVE,
    SignalKey.TEMPO_RESPOSTA: SignalPolarity.NEUTRAL,
    SignalKey.TAMANHO_MENSAGEM: SignalPolarity.NEUTRAL,
    SignalKey.EMOJIS: SignalPolarity.NEUTRAL,
    SignalKey.RESPOSTAS_OBJETIVAS: SignalPolarity.NEUTRAL,
    SignalKey.PERIODOS_SEM_CONVERSAR: SignalPolarity.NEUTRAL,
    SignalKey.RESPOSTAS_CURTAS: SignalPolarity.NEGATIVE,
    SignalKey.FALTA_RECIPROCIDADE: SignalPolarity.NEGATIVE,
    SignalKey.IGNORA_PERGUNTAS: SignalPolarity.NEGATIVE,
    SignalKey.EVITA_ASSUNTOS: SignalPolarity.NEGATIVE,
    SignalKey.RECUSA_ENCONTROS: SignalPolarity.NEGATIVE,
    SignalKey.FALTA_INTERESSE_EXPLICITA: SignalPolarity.NEGATIVE,
}


@dataclass(slots=True, frozen=True)
class DetectedSignal:
    key: SignalKey
    participant: str
    strength: float
    message_ids: tuple[UUID, ...]
    observation: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ClassifiedSignal:
    key: SignalKey
    label: str
    polarity: SignalPolarity
    participant: str
    strength: float
    message_ids: tuple[UUID, ...]
    observation: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ReciprocityAnalysis:
    initiation_balance: float
    message_balance: float
    question_balance: float
    overall_score: float
    observation: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class InterestAssessment:
    interest_score: int
    interest_level: InterestLevel
    confidence_score: int
    positive_signals: tuple[ClassifiedSignal, ...]
    neutral_signals: tuple[ClassifiedSignal, ...]
    negative_signals: tuple[ClassifiedSignal, ...]
    reciprocity: ReciprocityAnalysis
    evidence: tuple[EvidenceRecord, ...]


@dataclass(slots=True, frozen=True)
class EvidenceRecord:
    signal_key: SignalKey
    signal_label: str
    polarity: SignalPolarity
    message_ids: tuple[UUID, ...]
    observation: str


@dataclass(slots=True, frozen=True)
class TimelinePeriod:
    key: str
    label: str
    message_count: int
    interest_score: int
    interest_level: InterestLevel
    confidence_score: int
    positive_count: int
    neutral_count: int
    negative_count: int
    summary_observation: str

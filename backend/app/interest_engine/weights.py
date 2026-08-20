"""Pesos e limites configuráveis do Interest Engine.

Estes valores são um primeiro palpite — calibração real exigirá dados de produção.
"""

from app.interest_engine.types import SignalKey

# Score base neutro antes de aplicar sinais.
BASE_INTEREST_SCORE = 50

# Nenhum sinal isolado pode mover o score mais que este valor (em pontos).
MAX_SINGLE_SIGNAL_CONTRIBUTION = 12

# Contribuição máxima combinada por polaridade (evita domínio de uma categoria).
MAX_POSITIVE_TOTAL_CONTRIBUTION = 35
MAX_NEGATIVE_TOTAL_CONTRIBUTION = 35

POSITIVE_SIGNAL_WEIGHTS: dict[SignalKey, float] = {
    SignalKey.INICIA_CONVERSAS: 0.14,
    SignalKey.FAZ_PERGUNTAS: 0.12,
    SignalKey.MANTEM_ASSUNTOS: 0.08,
    SignalKey.RESPONDE_ELABORADO: 0.10,
    SignalKey.RETOMA_ASSUNTOS: 0.08,
    SignalKey.COMPARTILHA_INFORMACAO: 0.10,
    SignalKey.RECIPROCIDADE_INICIATIVA: 0.12,
    SignalKey.PROPOE_ACEITA_PLANOS: 0.10,
    SignalKey.MANTEM_CONTINUIDADE: 0.08,
    SignalKey.ENVIA_AUDIO_ESPONTANEO: 0.08,
}

NEGATIVE_SIGNAL_WEIGHTS: dict[SignalKey, float] = {
    SignalKey.RESPOSTAS_CURTAS: 0.14,
    SignalKey.FALTA_RECIPROCIDADE: 0.16,
    SignalKey.IGNORA_PERGUNTAS: 0.14,
    SignalKey.EVITA_ASSUNTOS: 0.10,
    SignalKey.RECUSA_ENCONTROS: 0.12,
    SignalKey.FALTA_INTERESSE_EXPLICITA: 0.16,
}

# Limiares heurísticos para detecção (ajustáveis).
SHORT_MESSAGE_CHARS = 18
ELABORATE_MESSAGE_CHARS = 80
SPONTANEOUS_SHARE_CHARS = 100
MIN_TOPIC_OVERLAP_TOKENS = 2
INITIATION_IMBALANCE_RATIO = 0.35
QUESTION_IGNORE_MIN_LENGTH = 8
EMOJI_PATTERN_CHARS = ("😀", "😊", "❤", "👍", "🙂", "😂", "🥰", "😍")

# Confidence — volume mínimo para confiança plena.
CONFIDENCE_FULL_MESSAGE_COUNT = 50
CONFIDENCE_FULL_SPAN_DAYS = 14
CONFIDENCE_FULL_SIGNAL_COUNT = 5
CONFIDENCE_LOW_VOLUME_CAP = 35
CONFIDENCE_LOW_VOLUME_MESSAGE_THRESHOLD = 12

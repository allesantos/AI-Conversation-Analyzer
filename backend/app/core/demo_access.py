from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.models.ai_usage import AIUsage
from app.models.user import User

DEMO_AI_LOCKED_CODE = "DEMO_AI_LOCKED"
DEMO_QUOTA_EXCEEDED_CODE = "DEMO_QUOTA_EXCEEDED"

LLM_OPERATIONS = ("analyze", "ask", "suggestions")
TRANSCRIPTION_OPERATIONS = ("transcription",)

DEMO_AI_LOCKED_MESSAGE = (
    "Esta é uma versão demo. O uso de IA (análise, perguntas, sugestões e "
    "transcrição) está bloqueado. Entre em contato para solicitar liberação: "
    "alledesenvolvimento@gmail.com"
)


class DemoAiLockedError(ForbiddenError):
    code = DEMO_AI_LOCKED_CODE

    def __init__(self, message: str = DEMO_AI_LOCKED_MESSAGE) -> None:
        super().__init__(message)


class DemoQuotaExceededError(ForbiddenError):
    code = DEMO_QUOTA_EXCEEDED_CODE

    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass(frozen=True)
class DemoQuotaSnapshot:
    unlimited: bool
    llm_used: int
    llm_limit: int
    audio_seconds_used: float
    audio_seconds_limit: float

    @property
    def llm_remaining(self) -> int | None:
        if self.unlimited:
            return None
        return max(0, self.llm_limit - self.llm_used)

    @property
    def audio_seconds_remaining(self) -> float | None:
        if self.unlimited:
            return None
        return max(0.0, self.audio_seconds_limit - self.audio_seconds_used)


def is_demo_owner_email(email: str, settings: Settings) -> bool:
    return email.lower() == settings.demo_owner_email.lower()


def user_has_ai_access(user: User, settings: Settings) -> bool:
    if user.ai_access_enabled:
        return True
    return is_demo_owner_email(user.email, settings)


def ensure_ai_access(user: User, settings: Settings) -> None:
    if not user_has_ai_access(user, settings):
        raise DemoAiLockedError()


def _month_start_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def count_monthly_llm_calls(session: AsyncSession, user_id: UUID) -> int:
    since = _month_start_utc()
    result = await session.execute(
        select(func.count())
        .select_from(AIUsage)
        .where(
            AIUsage.user_id == user_id,
            AIUsage.created_at >= since,
            AIUsage.operation.in_(LLM_OPERATIONS),
        )
    )
    return int(result.scalar_one() or 0)


async def sum_monthly_audio_seconds(session: AsyncSession, user_id: UUID) -> float:
    since = _month_start_utc()
    result = await session.execute(
        select(func.coalesce(func.sum(AIUsage.audio_seconds), 0.0))
        .select_from(AIUsage)
        .where(
            AIUsage.user_id == user_id,
            AIUsage.created_at >= since,
            AIUsage.operation.in_(TRANSCRIPTION_OPERATIONS),
        )
    )
    return float(result.scalar_one() or 0.0)


async def get_demo_quota(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> DemoQuotaSnapshot:
    if is_demo_owner_email(user.email, settings):
        return DemoQuotaSnapshot(
            unlimited=True,
            llm_used=0,
            llm_limit=0,
            audio_seconds_used=0.0,
            audio_seconds_limit=0.0,
        )

    llm_used = await count_monthly_llm_calls(session, user.id)
    audio_used = await sum_monthly_audio_seconds(session, user.id)
    return DemoQuotaSnapshot(
        unlimited=False,
        llm_used=llm_used,
        llm_limit=settings.demo_unlocked_monthly_llm_calls,
        audio_seconds_used=audio_used,
        audio_seconds_limit=float(settings.demo_unlocked_monthly_transcription_seconds),
    )


async def ensure_llm_quota(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> None:
    ensure_ai_access(user, settings)
    if is_demo_owner_email(user.email, settings):
        return

    used = await count_monthly_llm_calls(session, user.id)
    limit = settings.demo_unlocked_monthly_llm_calls
    if used >= limit:
        raise DemoQuotaExceededError(
            f"Limite da demo atingido ({limit} usos de IA neste mês). "
            f"Entre em contato para ampliar: {settings.demo_contact_email}"
        )


async def ensure_transcription_quota(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> None:
    ensure_ai_access(user, settings)
    if is_demo_owner_email(user.email, settings):
        return

    used = await sum_monthly_audio_seconds(session, user.id)
    limit = float(settings.demo_unlocked_monthly_transcription_seconds)
    if used >= limit:
        minutes = int(limit // 60)
        raise DemoQuotaExceededError(
            f"Limite de áudio da demo atingido ({minutes} min neste mês). "
            f"Entre em contato para ampliar: {settings.demo_contact_email}"
        )

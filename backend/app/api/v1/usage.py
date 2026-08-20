from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.repositories.ai_usage import AIUsageRepository
from app.schemas.usage import UsageRecord, UsageSummary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageSummary)
async def get_usage(
    current_user: CurrentUser,
    session: DbSession,
) -> UsageSummary:
    rows = await AIUsageRepository(session).list_for_user(current_user.id)
    records = [UsageRecord.model_validate(r) for r in rows]
    return UsageSummary(
        total_records=len(records),
        total_input_tokens=sum(r.input_tokens for r in records),
        total_output_tokens=sum(r.output_tokens for r in records),
        total_audio_seconds=sum(r.audio_seconds or 0 for r in records),
        total_estimated_cost=round(sum(r.estimated_cost for r in records), 6),
        records=records,
    )

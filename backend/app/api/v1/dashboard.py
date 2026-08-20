from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
async def get_dashboard(
    current_user: CurrentUser,
    session: DbSession,
) -> DashboardSummary:
    return await DashboardService(session).get_summary(current_user.id)

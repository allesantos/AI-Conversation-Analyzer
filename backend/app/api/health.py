from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.requests import Request

from app.api.deps import DbSession
from app.core.demo_access import DemoAiLockedError, DemoQuotaExceededError
from app.core.exceptions import AppError, ProcessingError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        if isinstance(exc, ProcessingError):
            return JSONResponse(
                status_code=exc.status_code,
                content={"status": exc.processing_status, "message": exc.message},
            )
        if isinstance(exc, (DemoAiLockedError, DemoQuotaExceededError)):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message, "code": exc.code},
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def register_health_routes(app: FastAPI) -> None:
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def ready(session: DbSession) -> dict[str, str]:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}

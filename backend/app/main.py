from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import register_error_handlers, register_health_routes
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="API REST do AI Conversation Analyzer.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(application)
    register_health_routes(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()

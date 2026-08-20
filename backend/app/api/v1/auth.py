from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(session: DbSession, settings: AppSettings) -> AuthService:
    return AuthService(session, settings)


AuthSvc = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthSvc) -> AuthResponse:
    return await service.register(payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, service: AuthSvc) -> AuthResponse:
    return await service.login(payload)


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)

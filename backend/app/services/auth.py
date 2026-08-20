from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import hash_password, verify_password
from app.core.config import Settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserRead


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> AuthResponse:
        existing = await self.users.get_by_email(payload.email)
        if existing is not None:
            raise ConflictError("Já existe uma conta com este e-mail")

        user = User(
            email=payload.email.lower(),
            hashed_password=hash_password(payload.password),
            terms_accepted_at=datetime.now(UTC),
        )
        user = await self.users.add(user)
        await self.session.commit()
        return self._to_auth_response(user)

    async def login(self, payload: LoginRequest) -> AuthResponse:
        user = await self.users.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("E-mail ou senha inválidos")
        return self._to_auth_response(user)

    def _to_auth_response(self, user: User) -> AuthResponse:
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            settings=self.settings,
        )
        return AuthResponse(access_token=token, user=UserRead.model_validate(user))

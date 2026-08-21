from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import hash_password, verify_password
from app.core.config import Settings
from app.core.demo_access import get_demo_quota, is_demo_owner_email, user_has_ai_access
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import AuthResponse, DemoQuotaRead, LoginRequest, RegisterRequest, UserRead


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> AuthResponse:
        existing = await self.users.get_by_email(payload.email)
        if existing is not None:
            raise ConflictError("Já existe uma conta com este e-mail")

        email = payload.email.lower()
        user = User(
            email=email,
            hashed_password=hash_password(payload.password),
            terms_accepted_at=datetime.now(UTC),
            ai_access_enabled=is_demo_owner_email(email, self.settings),
        )
        user = await self.users.add(user)
        await self.session.commit()
        return await self._to_auth_response(user)

    async def login(self, payload: LoginRequest) -> AuthResponse:
        user = await self.users.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("E-mail ou senha inválidos")
        return await self._to_auth_response(user)

    async def build_user_read(self, user: User) -> UserRead:
        user_read = UserRead.model_validate(user)
        if not user_has_ai_access(user, self.settings):
            return user_read.model_copy(update={"ai_access_enabled": False, "demo_quota": None})

        quota = await get_demo_quota(self.session, user, self.settings)
        return user_read.model_copy(
            update={
                "ai_access_enabled": True,
                "demo_quota": DemoQuotaRead(
                    unlimited=quota.unlimited,
                    llm_used=quota.llm_used,
                    llm_limit=quota.llm_limit,
                    audio_seconds_used=quota.audio_seconds_used,
                    audio_seconds_limit=quota.audio_seconds_limit,
                ),
            }
        )

    async def _to_auth_response(self, user: User) -> AuthResponse:
        token = create_access_token(
            user_id=user.id,
            email=user.email,
            settings=self.settings,
        )
        return AuthResponse(access_token=token, user=await self.build_user_read(user))

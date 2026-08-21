"""Tests for demo AI access gating and monthly quota."""

from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import get_db
from app.models.ai_usage import AIUsage
from app.models.user import User
from tests.conftest import auth_headers


async def test_register_defaults_ai_locked(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "demo@example.com",
            "password": "password123",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["ai_access_enabled"] is False


async def test_owner_register_is_unlocked(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alledesenvolvimento@gmail.com",
            "password": "password123",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201
    body = response.json()["user"]
    assert body["ai_access_enabled"] is True
    assert body["demo_quota"]["unlimited"] is True


async def test_analyze_blocked_for_demo_user(client: AsyncClient) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "locked@example.com",
            "password": "password123",
            "terms_accepted": True,
        },
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Demo"},
    )
    conversation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "DEMO_AI_LOCKED"
    assert "alledesenvolvimento@gmail.com" in body["detail"]


async def test_analyze_blocked_when_monthly_llm_quota_exceeded(app, client: AsyncClient) -> None:
    headers = await auth_headers(client, "quota@example.com")

    async for session in app.dependency_overrides[get_db]():
        user = (
            await session.execute(select(User).where(User.email == "quota@example.com"))
        ).scalar_one()
        user.ai_access_enabled = True
        limit = Settings().demo_unlocked_monthly_llm_calls
        for _ in range(limit):
            session.add(
                AIUsage(
                    user_id=user.id,
                    conversation_id=None,
                    operation="analyze",
                    provider="openai",
                    model="gpt-4o-mini",
                    input_tokens=10,
                    output_tokens=5,
                    estimated_cost=0.0,
                )
            )
        await session.commit()
        break

    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Quota"},
    )
    conversation_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/analyze",
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "DEMO_QUOTA_EXCEEDED"

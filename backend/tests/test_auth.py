from httpx import AsyncClient


async def test_register_creates_user_and_returns_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ana@example.com",
            "password": "password123",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "ana@example.com"


async def test_register_requires_terms(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ana@example.com",
            "password": "password123",
            "terms_accepted": False,
        },
    )
    assert response.status_code == 422


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    payload = {
        "email": "ana@example.com",
        "password": "password123",
        "terms_accepted": True,
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    second = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


async def test_login_success(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ana@example.com",
            "password": "password123",
            "terms_accepted": True,
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_invalid_credentials(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )
    assert response.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client: AsyncClient) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ana@example.com",
            "password": "password123",
            "terms_accepted": True,
        },
    )
    token = register.json()["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "ana@example.com"

from httpx import AsyncClient

from tests.conftest import auth_headers


async def test_create_and_list_conversations(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ana@example.com")
    created = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Conversa com João"},
    )
    assert created.status_code == 201
    assert created.json()["title"] == "Conversa com João"

    listed = await client.get("/api/v1/conversations", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Conversa com João"


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/conversations")
    assert response.status_code == 401


async def test_user_cannot_see_another_users_conversations(client: AsyncClient) -> None:
    ana = await auth_headers(client, "ana@example.com")
    bruno = await auth_headers(client, "bruno@example.com")

    created = await client.post(
        "/api/v1/conversations",
        headers=ana,
        json={"title": "Privada da Ana"},
    )
    assert created.status_code == 201

    listed = await client.get("/api/v1/conversations", headers=bruno)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    assert listed.json()["items"] == []


async def test_user_cannot_delete_another_users_conversation(client: AsyncClient) -> None:
    ana = await auth_headers(client, "ana@example.com")
    bruno = await auth_headers(client, "bruno@example.com")

    created = await client.post(
        "/api/v1/conversations",
        headers=ana,
        json={"title": "Privada da Ana"},
    )
    conversation_id = created.json()["id"]

    deleted = await client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=bruno,
    )
    assert deleted.status_code == 404

    listed = await client.get("/api/v1/conversations", headers=ana)
    assert listed.json()["total"] == 1


async def test_owner_can_delete_conversation(client: AsyncClient) -> None:
    ana = await auth_headers(client, "ana@example.com")
    created = await client.post(
        "/api/v1/conversations",
        headers=ana,
        json={"title": "Para excluir"},
    )
    conversation_id = created.json()["id"]

    deleted = await client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=ana,
    )
    assert deleted.status_code == 204

    listed = await client.get("/api/v1/conversations", headers=ana)
    assert listed.json()["total"] == 0

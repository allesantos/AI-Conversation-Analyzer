from pathlib import Path

from httpx import AsyncClient

from tests.conftest import auth_headers

FIXTURES = Path(__file__).parent / "fixtures" / "whatsapp"


def _txt(name: str) -> tuple[str, bytes, str]:
    path = FIXTURES / name
    return (name, path.read_bytes(), "text/plain")


async def _create_conversation(client: AsyncClient, headers: dict[str, str], title: str) -> str:
    created = await client.post("/api/v1/conversations", headers=headers, json={"title": title})
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def test_import_and_get_conversation_with_pagination(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_conversation(client, headers, "Chat fictício")

    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("standard_oneline.txt")},
        data={"owner_name": "Marina Costa"},
    )
    assert imported.status_code == 200, imported.text
    summary = imported.json()
    assert summary["total_messages"] == 3
    assert summary["skipped_lines"] == 0
    names = {item["name"]: item["role"] for item in summary["participants"]}
    assert names["Marina Costa"] == "OWNER"
    assert names["Pedro Almeida"] == "OTHER"
    assert summary["first_message_at"].startswith("2026-08-18T09:15:00")
    assert summary["last_message_at"].startswith("2026-08-18T09:17:00")

    detail = await client.get(f"/api/v1/conversations/{conversation_id}?limit=2", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "Chat fictício"
    assert body["total_messages"] == 3
    assert len(body["messages"]) == 2
    assert body["messages"][0]["content"] == "Oi Pedro, tudo bem?"
    assert body["messages"][0]["sender_name"] == "Marina Costa"

    page_two = await client.get(
        f"/api/v1/conversations/{conversation_id}?offset=2&limit=2",
        headers=headers,
    )
    assert page_two.status_code == 200
    assert len(page_two.json()["messages"]) == 1
    assert page_two.json()["messages"][0]["content"] == "Também. Vamos marcar aquele café?"


async def test_import_multiline_system_attachments_and_malformed(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_conversation(client, headers, "Edge cases")

    multiline = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("multiline.txt")},
    )
    assert multiline.status_code == 200
    assert multiline.json()["total_messages"] == 3
    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert "Rua das Palmeiras, 120" in detail.json()["messages"][0]["content"]

    system = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("system.txt")},
    )
    assert system.status_code == 200
    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    types = [item["type"] for item in detail.json()["messages"]]
    assert types == ["SYSTEM", "SYSTEM", "SYSTEM", "TEXT"]
    assert detail.json()["messages"][0]["sender_id"] is None

    attachments = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("attachments.txt")},
    )
    assert attachments.status_code == 200
    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.json()["messages"][0]["type"] == "IMAGE"
    assert detail.json()["messages"][2]["type"] == "AUDIO"

    malformed = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("malformed.txt")},
    )
    assert malformed.status_code == 200
    body = malformed.json()
    assert body["total_messages"] == 2
    assert body["skipped_lines"] == 3


async def test_import_empty_and_single_message(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_conversation(client, headers, "Vazia")

    empty = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("empty.txt")},
    )
    assert empty.status_code == 200
    assert empty.json()["total_messages"] == 0
    assert empty.json()["first_message_at"] is None

    single = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("single_message.txt")},
    )
    assert single.status_code == 200
    assert single.json()["total_messages"] == 1


async def test_reimport_replaces_previous_messages(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_conversation(client, headers, "Reimport")

    await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("standard_oneline.txt")},
    )
    second = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("single_message.txt")},
    )
    assert second.status_code == 200
    assert second.json()["total_messages"] == 1

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.json()["total_messages"] == 1
    assert detail.json()["messages"][0]["content"] == "Só esta mensagem."


async def test_import_rejects_non_txt(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_conversation(client, headers, "Arquivo errado")
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": ("foto.jpg", b"not-a-chat", "image/jpeg")},
    )
    assert response.status_code == 400


async def test_import_does_not_leak_between_users(client: AsyncClient) -> None:
    ana = await auth_headers(client, "ana@example.com")
    bruno = await auth_headers(client, "bruno@example.com")

    ana_id = await _create_conversation(client, ana, "Privada da Ana")
    bruno_id = await _create_conversation(client, bruno, "Privada do Bruno")

    imported = await client.post(
        f"/api/v1/conversations/{ana_id}/import",
        headers=ana,
        files={"file": _txt("standard_oneline.txt")},
    )
    assert imported.status_code == 200

    leaked_get = await client.get(f"/api/v1/conversations/{ana_id}", headers=bruno)
    assert leaked_get.status_code == 404

    leaked_import = await client.post(
        f"/api/v1/conversations/{ana_id}/import",
        headers=bruno,
        files={"file": _txt("single_message.txt")},
    )
    assert leaked_import.status_code == 404

    bruno_detail = await client.get(f"/api/v1/conversations/{bruno_id}", headers=bruno)
    assert bruno_detail.status_code == 200
    assert bruno_detail.json()["total_messages"] == 0

    ana_detail = await client.get(f"/api/v1/conversations/{ana_id}", headers=ana)
    assert ana_detail.status_code == 200
    assert ana_detail.json()["total_messages"] == 3
    assert ana_detail.json()["messages"][0]["content"] == "Oi Pedro, tudo bem?"


async def test_import_ios_brackets_format(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ana@example.com")
    conversation_id = await _create_conversation(client, headers, "Chat iOS fictício")

    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": _txt("ios_brackets.txt")},
        data={"owner_name": "Marina Costa"},
    )
    assert imported.status_code == 200, imported.text
    summary = imported.json()
    assert summary["total_messages"] == 5
    assert summary["skipped_lines"] == 0
    names = {item["name"]: item["role"] for item in summary["participants"]}
    assert names["Marina Costa"] == "OWNER"
    assert names["Pedro Almeida"] == "OTHER"
    assert summary["first_message_at"].startswith("2026-08-18T08:00:00")
    assert summary["last_message_at"].startswith("2026-08-18T09:18:22")

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["messages"][0]["type"] == "SYSTEM"
    assert body["messages"][0]["sender_id"] is None
    assert "Rua das Palmeiras, 120" in body["messages"][2]["content"]
    assert body["messages"][3]["type"] == "IMAGE"

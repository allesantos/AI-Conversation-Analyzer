from __future__ import annotations

from datetime import UTC

from app.conversation.metric_message import MetricMessage


def messages_to_whatsapp_txt(messages: list[MetricMessage]) -> bytes:
    ordered = sorted(messages, key=lambda item: (item.timestamp, str(item.id)))
    lines: list[str] = []
    for item in ordered:
        timestamp = item.timestamp.astimezone(UTC).strftime("%d/%m/%Y %H:%M")
        sender = item.sender_name or "Desconhecido"
        lines.append(f"{timestamp} - {sender}: {item.content}")
    return "\n".join(lines).encode("utf-8")


async def import_messages_scenario(
    client,
    headers: dict[str, str],
    *,
    title: str,
    messages: list[MetricMessage],
    owner_name: str = "Alex",
) -> str:
    created = await client.post("/api/v1/conversations", headers=headers, json={"title": title})
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/import",
        headers=headers,
        files={"file": ("cenario.txt", messages_to_whatsapp_txt(messages), "text/plain")},
        data={"owner_name": owner_name},
    )
    assert imported.status_code == 200, imported.text
    return conversation_id

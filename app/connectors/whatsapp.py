from __future__ import annotations

from typing import Any

import httpx

from app import bus
from app.config import get_settings
from app.household import store


async def send_text(to: str, text: str) -> dict[str, Any]:
    member = store.member_by_alias(to) or store.member_by_phone(to)
    phone = member["phone"] if member else to
    digits = "".join(ch for ch in str(phone) if ch.isdigit())[-10:]
    alias = member["alias"] if member else "unknown"
    language = member["language"] if member else "en"

    s = get_settings()
    result: dict[str, Any] = {
        "to": digits,
        "alias": alias,
        "name": member["name"] if member else digits,
        "language": language,
        "text": text,
        "channel": "stage",
    }

    if s.wa_access_token and s.wa_phone_number_id:
        url = (
            f"https://graph.facebook.com/{s.wa_graph_version}/"
            f"{s.wa_phone_number_id}/messages"
        )
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": f"91{digits}",
            "type": "text",
            "text": {"preview_url": True, "body": text},
        }
        await bus.emit("http_request", {"partner": "whatsapp", "method": "POST", "url": url, "body": body})
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {s.wa_access_token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
        await bus.emit(
            "http_response",
            {"partner": "whatsapp", "status": resp.status_code, "body": data, "url": url},
        )
        result["channel"] = "whatsapp_cloud"
        result["api"] = data
        result["http_status"] = resp.status_code
    else:
        await bus.emit(
            "agent_note",
            {"text": "WhatsApp Cloud API keys missing — message shown on the stage pane only."},
        )

    try:
        from app.connectors import gnani

        spoken = await gnani.speak(text, language)
        result["tts"] = {k: spoken[k] for k in ("voice", "language", "bytes", "endpoint")}
        result["audio_b64"] = spoken["audio_b64"]
    except Exception as exc:  # noqa: BLE001 — still deliver the text
        result["tts_error"] = str(exc)
        await bus.emit("agent_note", {"text": f"Gnani TTS skipped: {exc}"})

    await bus.emit("whatsapp_out", result)
    return {k: v for k, v in result.items() if k != "audio_b64"}


async def download_media(media_id: str) -> tuple[bytes, str]:
    s = get_settings()
    if not s.wa_access_token:
        raise RuntimeError("WA_ACCESS_TOKEN required to download a voice note")
    meta_url = f"https://graph.facebook.com/{s.wa_graph_version}/{media_id}"
    headers = {"Authorization": f"Bearer {s.wa_access_token}"}
    async with httpx.AsyncClient(timeout=30) as client:
        meta = await client.get(meta_url, headers=headers)
        meta.raise_for_status()
        url = meta.json()["url"]
        audio = await client.get(url, headers=headers)
        audio.raise_for_status()
    mime = audio.headers.get("content-type", "audio/ogg")
    ext = "ogg" if "ogg" in mime else "mp3"
    return audio.content, f"voice.{ext}"


def parse_inbound(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            for msg in value.get("messages", []) or []:
                from_phone = "".join(ch for ch in str(msg.get("from", "")) if ch.isdigit())[-10:]
                member = store.member_by_phone(from_phone)
                item = {
                    "from": from_phone,
                    "name": member["name"] if member else from_phone,
                    "alias": member["alias"] if member else "unknown",
                    "type": msg.get("type"),
                    "id": msg.get("id"),
                }
                if msg.get("type") == "text":
                    item["text"] = (msg.get("text") or {}).get("body", "")
                elif msg.get("type") == "audio":
                    item["media_id"] = (msg.get("audio") or {}).get("id")
                    item["voice"] = True
                events.append(item)
    return events

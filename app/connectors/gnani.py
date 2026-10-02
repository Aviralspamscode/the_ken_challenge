from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

import httpx

from app import bus
from app.config import get_settings


class GnaniError(RuntimeError):
    pass


def _headers_platform() -> dict[str, str]:
    s = get_settings()
    if not s.gnani_platform_api_key:
        raise GnaniError(
            "GNANI_PLATFORM_API_KEY is missing. Create an API key with agents + conversations "
            "permissions at app.gnani.ai and set GNANI_BOT_ID."
        )
    return {"x-api-key": s.gnani_platform_api_key, "Content-Type": "application/json"}


async def trigger_call(phone: str, name: str, client_reference_id: str) -> dict[str, Any]:
    s = get_settings()
    if not s.gnani_bot_id:
        raise GnaniError("GNANI_BOT_ID is missing. Copy the Hindi agent id from app.gnani.ai.")
    digits = "".join(ch for ch in phone if ch.isdigit())[-10:]
    url = (
        f"{s.gnani_platform_base}/v1/agents/{s.gnani_bot_id}/trigger_call"
        f"?environment={s.gnani_environment}"
    )
    body = {
        "phone": digits,
        "countryCode": "+91",
        "name": name,
        "clientReferenceId": client_reference_id,
    }
    await bus.emit("http_request", {"partner": "gnani", "method": "POST", "url": url, "body": body})
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=_headers_platform(), json=body)
        data = _safe_json(resp)
    await bus.emit(
        "http_response",
        {"partner": "gnani", "status": resp.status_code, "body": data, "url": url},
    )
    if resp.status_code >= 400:
        raise GnaniError(f"trigger_call {resp.status_code}: {data}")
    return data


async def find_conversation(client_reference_id: str, attempts: int = 12, delay: float = 5.0) -> str | None:
    s = get_settings()
    url = f"{s.gnani_platform_base}/v1/conversations/logs?environment={s.gnani_environment}"
    if s.gnani_bot_id:
        url += f"&botId={s.gnani_bot_id}"
    body = {"pageNo": 1, "pageSize": 20, "searchTerm": client_reference_id}
    for i in range(attempts):
        await bus.emit(
            "http_request",
            {"partner": "gnani", "method": "POST", "url": url, "body": body, "poll": i + 1},
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=_headers_platform(), json=body)
            data = _safe_json(resp)
        await bus.emit(
            "http_response",
            {"partner": "gnani", "status": resp.status_code, "body": data, "url": url, "poll": i + 1},
        )
        rows = ((data.get("response") or {}).get("data")) or []
        if rows:
            return str(rows[0].get("conversationId"))
        await asyncio.sleep(delay)
    return None


async def conversation_stats(conversation_id: str) -> dict[str, Any]:
    s = get_settings()
    url = f"{s.gnani_platform_base}/v1/conversations/{conversation_id}/stats"
    await bus.emit("http_request", {"partner": "gnani", "method": "GET", "url": url})
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_headers_platform())
        data = _safe_json(resp)
    await bus.emit(
        "http_response",
        {"partner": "gnani", "status": resp.status_code, "body": data, "url": url},
    )
    if resp.status_code >= 400:
        raise GnaniError(f"stats {resp.status_code}: {data}")
    return data


async def synthesize(text: str, language: str = "hi-IN", voice: str = "Nalini") -> bytes:
    s = get_settings()
    key = s.stt_key
    if not key:
        raise GnaniError("GNANI_API_KEY missing — needed for Timbre TTS.")
    url = f"{s.gnani_stt_base}/api/v1/tts/inference"
    body = {
        "text": text,
        "voice": voice,
        "model": "timbre-v2.5",
        "language": language,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 22050,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    await bus.emit("http_request", {"partner": "gnani-tts", "method": "POST", "url": url, "body": {k: v for k, v in body.items() if k != "audio_config"}})
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers={"X-API-Key-ID": key, "Content-Type": "application/json"}, json=body)
    await bus.emit(
        "http_response",
        {"partner": "gnani-tts", "status": resp.status_code, "url": url, "bytes": len(resp.content)},
    )
    if resp.status_code >= 400:
        raise GnaniError(f"tts {resp.status_code}: {resp.text[:400]}")
    return resp.content


async def speak(text: str, language: str = "hi", voice: str | None = None) -> dict[str, Any]:
    """Gnani Timbre: text in, wav out. Used for WhatsApp lines and the live call."""
    lang = "hi-IN" if str(language).lower().startswith("hi") else "en-IN"
    chosen = voice or ("Nalini" if lang == "hi-IN" else "Kaveri")
    audio = await synthesize(text, lang, chosen)
    return {
        "voice": chosen,
        "language": lang,
        "bytes": len(audio),
        "audio_b64": base64.b64encode(audio).decode("ascii"),
        "endpoint": "POST https://api.vachana.ai/api/v1/tts/inference",
    }


async def place_call_and_wait(phone: str, name: str, reason: str) -> dict[str, Any]:
    s = get_settings()
    if not (s.gnani_platform_api_key and s.gnani_bot_id):
        from app.connectors.voice_booth import booth

        return await booth.open(phone=phone, name=name, reason=reason)

    ref = "gp-" + "".join(ch if ch.isalnum() else "-" for ch in reason)[:40]
    trigger = await trigger_call(phone, name, ref)
    await bus.emit("agent_note", {"text": f"Gnani call placed to {name}. Waiting for conversation id…"})
    conversation_id = await find_conversation(ref)
    if not conversation_id:
        return {
            "trigger": trigger,
            "conversationId": None,
            "note": "Call triggered but conversationId not found yet. Feed the post-call webhook or poll again.",
        }
    # Stats can lag the hang-up by 30–60s
    stats = None
    for i in range(8):
        stats = await conversation_stats(conversation_id)
        rows = stats.get("response") or []
        row = rows[0] if rows else {}
        if row.get("callStatus") or row.get("overallCallDisposition"):
            break
        await asyncio.sleep(8)
        await bus.emit("agent_note", {"text": f"Waiting for Gnani stats ({i + 1})…"})
    return {"trigger": trigger, "conversationId": conversation_id, "stats": stats}


async def transcribe(audio_bytes: bytes, filename: str = "note.ogg", language_code: str = "hi-IN") -> dict[str, Any]:
    s = get_settings()
    key = s.stt_key
    if not key:
        raise GnaniError(
            "GNANI_STT_API_KEY / GNANI_API_KEY missing. Get X-API-Key-ID from the Gnani APIs dashboard "
            "or email speechstack@gnani.ai."
        )
    url = f"{s.gnani_stt_base}/stt/v3"
    await bus.emit(
        "http_request",
        {
            "partner": "gnani-stt",
            "method": "POST",
            "url": url,
            "body": {"language_code": language_code, "format": "transcribe", "filename": filename},
        },
    )
    files = {"audio_file": (filename, audio_bytes, "application/octet-stream")}
    data = {"language_code": language_code, "format": "transcribe"}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers={"X-API-Key-ID": key}, files=files, data=data)
        payload = _safe_json(resp)
    await bus.emit(
        "http_response",
        {"partner": "gnani-stt", "status": resp.status_code, "body": payload, "url": url},
    )
    if resp.status_code >= 400:
        raise GnaniError(f"stt {resp.status_code}: {payload}")
    return payload


async def transcribe_file(path: str | Path, language_code: str = "hi-IN") -> dict[str, Any]:
    p = Path(path)
    return await transcribe(p.read_bytes(), filename=p.name, language_code=language_code)


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text, "status_code": resp.status_code}

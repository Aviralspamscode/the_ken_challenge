from __future__ import annotations

import asyncio
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app import bus
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.runner import runner
from app.clock import clock
from app.config import ROOT, get_settings
from app.connectors import gnani, sheets, whatsapp
from app.connectors.curtain import desk
from app.connectors.voice_booth import booth
from app.household import store
from app import scenarios

STATIC = ROOT / "static"

app = FastAPI(title="Ghar Pass", version="0.3.0")
if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/setup")
async def setup_status() -> dict[str, Any]:
    s = get_settings()
    return {
        "clock": clock.label(),
        "model": s.llm_model,
        "provider": s.llm_provider,
        "keys": {
            "anthropic": bool(s.anthropic_api_key),
            "openai": bool(s.openai_api_key),
            "gnani_platform": bool(s.gnani_platform_api_key and s.gnani_bot_id),
            "gnani_stt": bool(s.stt_key),
            "whatsapp": bool(s.wa_access_token and s.wa_phone_number_id),
            "google_sheets": bool(s.google_service_account_file and s.google_sheet_id),
            "pine_labs_live": bool(s.pinelabs_live and s.pinelabs_client_id),
            "delhivery_live": bool(s.delhivery_live and s.delhivery_api_token),
        },
        "phones": {
            "ritika": s.ritika_phone,
            "sunita": s.sunita_phone,
            "ramesh": s.ramesh_phone,
        },
        "required_for_recording": [
            "ANTHROPIC_API_KEY + Claude model",
            "GNANI_PLATFORM_API_KEY + GNANI_BOT_ID + 3 whitelisted actor phones",
            "GNANI_STT_API_KEY (or GNANI_API_KEY)",
            "WA_ACCESS_TOKEN + WA_PHONE_NUMBER_ID + 3 test recipients",
            "GOOGLE_SERVICE_ACCOUNT_FILE + GOOGLE_SHEET_ID",
            "Public HTTPS tunnel (ngrok) for WhatsApp / Gnani webhooks",
        ],
        "curtain_ok": ["Delhivery", "Pine Labs"],
    }


@app.get("/api/state")
async def state() -> dict[str, Any]:
    return {
        "clock": clock.label(),
        "iso": clock.iso(),
        "household": store.snapshot(),
        "curtain": desk.open_requests(),
        "busy": runner.busy,
        "decisions": [e for e in bus.history() if e["kind"] == "decision"],
        "model": get_settings().llm_model,
        "provider": get_settings().llm_provider,
    }


@app.get("/api/events")
async def sse(request: Request):
    queue = bus.subscribe()

    async def gen():
        for event in bus.history():
            yield {"event": "message", "data": bus.dumps(event)}
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    yield {"event": "message", "data": bus.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(gen())


@app.get("/api/prompt")
async def prompt() -> dict[str, str]:
    s = get_settings()
    return {"system": SYSTEM_PROMPT, "model": s.llm_model, "provider": s.llm_provider}


@app.get("/api/scenarios")
async def list_scenarios() -> dict[str, Any]:
    return {"scenarios": scenarios.catalog()}


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    desk.clear()
    booth.clear()
    bus.clear()
    runner.reset()
    clock.reset()
    store.reset()
    await bus.emit("reset", {"clock": clock.iso()})
    return {"ok": True, "clock": clock.label()}


@app.post("/api/clock")
async def set_clock(body: dict[str, Any]) -> dict[str, Any]:
    if "iso" in body:
        scenarios.apply_clock(body["iso"])
    elif "minutes" in body:
        clock.advance(int(body["minutes"]))
    await bus.emit("clock", {"clock": clock.iso()})
    return {"clock": clock.label()}


@app.get("/api/call/{pid}/open")
async def call_open(pid: str) -> dict[str, Any]:
    try:
        return await booth.speak_opening(pid)
    except KeyError as exc:
        raise HTTPException(404, "unknown call") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Gnani TTS failed: {exc}") from exc


@app.post("/api/call/{pid}/hear")
async def call_hear(pid: str, audio: UploadFile = File(...)) -> dict[str, Any]:
    raw = await audio.read()
    try:
        return await booth.hear(pid, raw, audio.filename or "turn.webm")
    except KeyError as exc:
        raise HTTPException(404, "unknown call") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Call turn failed: {exc}") from exc


@app.post("/api/call/{pid}/hangup")
async def call_hangup(pid: str) -> dict[str, Any]:
    try:
        result = booth.hangup(pid)
    except KeyError as exc:
        raise HTTPException(404, "unknown call") from exc
    await bus.emit("call_ended", {"id": pid, "result": result})
    return result


@app.post("/api/curtain/{pid}")
async def resolve_curtain(pid: str, body: dict[str, Any]) -> dict[str, Any]:
    response = body.get("response")
    if not isinstance(response, dict):
        raise HTTPException(400, "Body must be {\"response\": { ... partner JSON ... }}")
    try:
        desk.resolve(pid, response)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    await bus.emit("curtain_response", {"id": pid, "response": response})
    return {"ok": True}


@app.post("/api/inject/{scenario_id}")
async def inject(scenario_id: str, background: BackgroundTasks) -> dict[str, Any]:
    meta = next((s for s in scenarios.catalog() if s["id"] == scenario_id), None)
    if not meta:
        raise HTTPException(404, f"unknown scenario {scenario_id}")
    scenarios.apply_clock(meta["clock"])
    event = scenarios.build(scenario_id)
    if scenario_id == "d4":
        spoken = event["payload"].get("transcript") or event["payload"].get("transcript_roman")
        if spoken:
            background.add_task(_announce_person, "sunita", spoken)
    background.add_task(runner.handle_event, event["title"], event["payload"], event["source"])
    return {"ok": True, "clock": clock.label(), "title": event["title"]}


@app.post("/api/event")
async def custom_event(body: dict[str, Any], background: BackgroundTasks) -> dict[str, Any]:
    title = body.get("title") or "Custom event"
    source = body.get("source") or "operator"
    payload = body.get("payload") or {}
    if body.get("iso"):
        scenarios.apply_clock(body["iso"])
    background.add_task(runner.handle_event, title, payload, source)
    return {"ok": True}


@app.post("/api/stage/message")
async def stage_message(body: dict[str, Any], background: BackgroundTasks) -> dict[str, Any]:
    alias = body.get("from") or "ritika"
    member = store.member_by_alias(alias)
    if not member:
        raise HTTPException(400, "unknown sender")
    text = body.get("text") or ""
    inbound = {"from": member["phone"], "alias": member["alias"], "name": member["name"], "text": text, "type": "text"}
    await _attach_person_voice(inbound, member)
    await bus.emit("whatsapp_in", inbound)
    store.clear_reply(member["phone"])
    background.add_task(
        runner.handle_event,
        f"WhatsApp from {member['name']}",
        {"from": member["phone"], "name": member["name"], "type": "text", "text": text},
        "WhatsApp → teammate on a real (or stage) phone",
    )
    return {"ok": True}


@app.post("/api/stage/voice")
async def stage_voice(
    background: BackgroundTasks,
    sender: str = Form("sunita"),
    audio: UploadFile = File(...),
) -> dict[str, Any]:
    member = store.member_by_alias(sender)
    if not member:
        raise HTTPException(400, "unknown sender")
    raw = await audio.read()
    try:
        stt = await gnani.transcribe(raw, audio.filename or "note.ogg", "hi-IN")
        transcript = stt.get("transcript") or ""
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Gnani STT failed: {exc}") from exc
    await bus.emit(
        "whatsapp_in",
        {
            "from": member["phone"],
            "alias": member["alias"],
            "name": member["name"],
            "type": "audio",
            "transcript": transcript,
        },
    )
    store.clear_reply(member["phone"])
    background.add_task(
        runner.handle_event,
        f"Voice note from {member['name']}",
        {
            "from": member["phone"],
            "name": member["name"],
            "type": "audio",
            "transcript": transcript,
            "stt": stt,
        },
        "WhatsApp → voice note → Gnani POST /stt/v3",
    )
    return {"ok": True, "transcript": transcript, "stt": stt}


@app.get("/webhooks/whatsapp")
async def wa_verify(request: Request) -> Any:
    s = get_settings()
    params = request.query_params
    if params.get("hub.verify_token") == s.wa_verify_token:
        return PlainTextResponse(params.get("hub.challenge") or "")
    return JSONResponse({"error": "verify token mismatch"}, status_code=403)


@app.post("/webhooks/whatsapp")
async def wa_inbound(request: Request, background: BackgroundTasks) -> dict[str, str]:
    payload = await request.json()
    await bus.emit("webhook", {"partner": "whatsapp", "payload": payload})
    for msg in whatsapp.parse_inbound(payload):
        if msg.get("voice") and msg.get("media_id"):
            try:
                audio, filename = await whatsapp.download_media(msg["media_id"])
                stt = await gnani.transcribe(audio, filename, "hi-IN")
                msg["transcript"] = stt.get("transcript")
                msg["stt"] = stt
            except Exception as exc:  # noqa: BLE001
                msg["stt_error"] = str(exc)
        await bus.emit("whatsapp_in", msg)
        store.clear_reply(msg["from"])
        background.add_task(
            runner.handle_event,
            f"WhatsApp from {msg['name']}",
            msg,
            "WhatsApp Cloud API webhook",
        )
    return {"status": "ok"}


@app.post("/webhooks/delhivery")
async def delhivery_hook(request: Request, background: BackgroundTasks) -> dict[str, str]:
    payload = await request.json()
    await bus.emit("webhook", {"partner": "delhivery", "payload": payload})
    background.add_task(
        runner.handle_event,
        "Delhivery push scan",
        payload,
        "webhook → Delhivery push scan",
    )
    return {"status": "ok"}


@app.post("/webhooks/pinelabs")
async def pinelabs_hook(request: Request, background: BackgroundTasks) -> dict[str, str]:
    payload = await request.json()
    await bus.emit("webhook", {"partner": "pine_labs", "payload": payload})
    background.add_task(
        runner.handle_event,
        "Pine Labs payment webhook",
        payload,
        "webhook → Pine Labs UAT",
    )
    return {"status": "ok"}


@app.post("/webhooks/gnani")
async def gnani_hook(request: Request, background: BackgroundTasks) -> dict[str, str]:
    payload = await request.json()
    await bus.emit("webhook", {"partner": "gnani", "payload": payload})
    background.add_task(
        runner.handle_event,
        "Gnani post-call webhook",
        payload,
        "webhook → Gnani conversation stats",
    )
    return {"status": "ok"}


async def _attach_person_voice(payload: dict[str, Any], member: dict[str, Any]) -> None:
    text = payload.get("text") or payload.get("transcript")
    if not text:
        return
    voice = {"ritika": "Kaveri", "sunita": "Poorvi", "ramesh": "Deepak"}.get(member.get("alias"), "Nalini")
    try:
        spoken = await gnani.speak(text, member.get("language") or "hi", voice)
        payload["audio_b64"] = spoken["audio_b64"]
        payload["tts"] = {k: spoken[k] for k in ("voice", "language", "bytes", "endpoint")}
    except Exception as exc:  # noqa: BLE001
        payload["tts_error"] = str(exc)


async def _announce_person(alias: str, text: str) -> None:
    member = store.member_by_alias(alias)
    if not member:
        return
    inbound = {
        "from": member["phone"],
        "alias": member["alias"],
        "name": member["name"],
        "text": text,
        "type": "audio",
    }
    await _attach_person_voice(inbound, member)
    await bus.emit("whatsapp_in", inbound)


@app.post("/api/sheets/bootstrap")
async def sheets_bootstrap() -> dict[str, Any]:
    return await sheets.bootstrap_sheet()


def run() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=False)


if __name__ == "__main__":
    run()

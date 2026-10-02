from __future__ import annotations

import asyncio
import base64
import json
import uuid
from typing import Any

from app import bus
from app.config import get_settings
from app.connectors import gnani

OPENING = {
    "home": "नमस्ते, मैं घर पास से बोल रही हूँ, रितिका जी की तरफ़ से। आज दो पार्सल आने वाले हैं। क्या आप घर पर हैं?",
    "pickup": "नमस्ते, मैं घर पास से बोल रही हूँ। क्या पिकअप वाले आए थे जूते लेने?",
}

TURN_PROMPT = """You are Ghar Pass, calling {name} in Hindi on a live phone.
Reason: {reason}

The person just said: {transcript}

Reply in 1-2 short Hindi sentences (Devanagari). Then decide a disposition.
Return ONLY JSON:
{{"reply": "...", "disposition": "HOME_CONFIRMED|NOT_HOME|PICKUP_NOT_ATTEMPTED|CALL_BACK", "done": true/false}}

HOME_CONFIRMED = they are home and will receive
NOT_HOME = they are out
PICKUP_NOT_ATTEMPTED = they say the courier never came
CALL_BACK = they want to be called later
Set done=true when you have enough to hang up.
"""


class VoiceBooth:
    def __init__(self) -> None:
        self.pending: dict[str, dict[str, Any]] = {}

    def _kind(self, reason: str) -> str:
        r = (reason or "").lower()
        return "pickup" if "pickup" in r or "pika" in r or "return" in r else "home"

    async def open(self, phone: str, name: str, reason: str) -> dict[str, Any]:
        pid = str(uuid.uuid4())[:8]
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        opening = OPENING[self._kind(reason)]
        self.pending[pid] = {
            "id": pid,
            "phone": phone,
            "name": name,
            "reason": reason,
            "opening": opening,
            "turns": [],
            "future": future,
        }
        await bus.emit(
            "call_booth",
            {"id": pid, "phone": phone, "name": name, "reason": reason, "opening": opening},
        )
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=600)
        except asyncio.TimeoutError:
            self.pending.pop(pid, None)
            return {"error": "call_timeout", "message": "Voice booth was not completed."}

    def get(self, pid: str) -> dict[str, Any]:
        rec = self.pending.get(pid)
        if not rec:
            raise KeyError(pid)
        return rec

    async def speak_opening(self, pid: str) -> dict[str, Any]:
        rec = self.get(pid)
        audio = await gnani.synthesize(rec["opening"])
        rec["turns"].append({"role": "assistant", "content": rec["opening"]})
        return {"text": rec["opening"], "audio_b64": base64.b64encode(audio).decode("ascii")}

    async def hear(self, pid: str, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        rec = self.get(pid)
        stt = await gnani.transcribe(audio_bytes, filename, "hi-IN")
        transcript = (stt.get("transcript") or "").strip()
        rec["turns"].append({"role": "user", "content": transcript, "stt": stt})
        decision = await _next_line(rec["name"], rec["reason"], transcript)
        rec["turns"].append({"role": "assistant", "content": decision["reply"], "disposition": decision.get("disposition")})
        rec["disposition"] = decision.get("disposition")
        audio = await gnani.synthesize(decision["reply"])
        await bus.emit(
            "call_turn",
            {"id": pid, "transcript": transcript, "reply": decision["reply"], "disposition": rec.get("disposition")},
        )
        return {
            "transcript": transcript,
            "stt": stt,
            "reply": decision["reply"],
            "disposition": rec.get("disposition"),
            "done": bool(decision.get("done")),
            "audio_b64": base64.b64encode(audio).decode("ascii"),
        }

    def hangup(self, pid: str) -> dict[str, Any]:
        rec = self.pending.pop(pid, None)
        if not rec:
            raise KeyError(pid)
        stats = {
            "callStatus": "ANSWERED",
            "overallCallDisposition": rec.get("disposition") or "HOME_CONFIRMED",
            "utteranceAnalytics": [
                {"role": t["role"], "content": t["content"], "detectedLanguage": "hindi"}
                for t in rec["turns"]
            ],
        }
        result = {
            "mode": "gnani_stt_tts_booth",
            "trigger": {
                "status": "success",
                "message": f"Live Gnani STT+TTS booth call to {rec['name']}",
            },
            "stats": {"status": "success", "response": [stats]},
        }
        fut: asyncio.Future = rec["future"]
        if not fut.done():
            fut.set_result(result)
        return result

    def clear(self) -> None:
        for rec in list(self.pending.values()):
            fut: asyncio.Future = rec["future"]
            if not fut.done():
                fut.cancel()
        self.pending.clear()


async def _next_line(name: str, reason: str, transcript: str) -> dict[str, Any]:
    settings = get_settings()
    prompt = TURN_PROMPT.format(name=name, reason=reason, transcript=transcript)
    raw = ""
    if settings.openai_api_key:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = resp.choices[0].message.content or ""
    elif settings.anthropic_api_key:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)
        resp = await asyncio.to_thread(
            client.messages.create,
            model=settings.anthropic_model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    else:
        raw = '{"reply": "ठीक है, धन्यवाद।", "disposition": "HOME_CONFIRMED", "done": true}'
    start, end = raw.find("{"), raw.rfind("}")
    try:
        data = json.loads(raw[start : end + 1] if start >= 0 else raw)
    except json.JSONDecodeError:
        data = {"reply": raw.strip() or "ठीक है।", "disposition": _guess(transcript), "done": True}
    data.setdefault("reply", "ठीक है, धन्यवाद।")
    data.setdefault("disposition", _guess(transcript))
    return data


def _guess(transcript: str) -> str:
    t = transcript.lower()
    if any(w in t for w in ("नहीं आए", "nahi aaye", "नही आए", "कोई नहीं")):
        return "PICKUP_NOT_ATTEMPTED"
    if any(w in t for w in ("नहीं", "बाहर", "मंदिर", "नही", "out")):
        return "NOT_HOME"
    if any(w in t for w in ("हाँ", "haan", "हूं", "हूँ", "ghar", "घर")):
        return "HOME_CONFIRMED"
    return "HOME_CONFIRMED"


booth = VoiceBooth()

from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from typing import Any

_subscribers: list[asyncio.Queue] = []
_history: deque[dict[str, Any]] = deque(maxlen=400)
_lock = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def emit(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "ts": _now_iso(),
        "kind": kind,
        "payload": payload or {},
    }
    async with _lock:
        _history.append(event)
        dead: list[asyncio.Queue] = []
        for q in _subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            if q in _subscribers:
                _subscribers.remove(q)
    return event


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


def history() -> list[dict[str, Any]]:
    return list(_history)


def clear() -> None:
    _history.clear()


def dumps(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, default=str)

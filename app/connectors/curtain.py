from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app import bus


class CurtainDesk:
    """Pauses curtain-played tools until a human pastes a doc-shaped JSON response.

    The operator cannot add instructions — only a JSON body is accepted as the tool result.
    """

    def __init__(self) -> None:
        self.pending: dict[str, dict[str, Any]] = {}

    async def ask(
        self,
        partner: str,
        method: str,
        endpoint: str,
        request: dict[str, Any],
        sample: dict[str, Any] | None = None,
        timeout: float = 600,
    ) -> dict[str, Any]:
        pid = str(uuid.uuid4())[:8]
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        record = {
            "id": pid,
            "partner": partner,
            "method": method,
            "endpoint": endpoint,
            "request": request,
            "sample": sample,
            "future": future,
        }
        self.pending[pid] = record
        await bus.emit(
            "curtain_request",
            {
                "id": pid,
                "partner": partner,
                "method": method,
                "endpoint": endpoint,
                "request": request,
                "sample": sample,
                "note": "Paste only the partner JSON. Do not add instructions to the agent.",
            },
        )
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.TimeoutError:
            self.pending.pop(pid, None)
            await bus.emit("curtain_timeout", {"id": pid, "partner": partner, "endpoint": endpoint})
            return {
                "error": "curtain_timeout",
                "message": f"No curtain response for {partner} {endpoint} within {timeout}s",
            }

    def resolve(self, pid: str, response: dict[str, Any]) -> dict[str, Any]:
        record = self.pending.pop(pid, None)
        if not record:
            raise KeyError(f"unknown curtain request {pid}")
        if not isinstance(response, dict):
            raise ValueError("curtain response must be a JSON object")
        future: asyncio.Future = record["future"]
        if not future.done():
            future.set_result(response)
        return {"ok": True, "id": pid}

    def open_requests(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r["id"],
                "partner": r["partner"],
                "method": r["method"],
                "endpoint": r["endpoint"],
                "request": r["request"],
                "sample": r["sample"],
            }
            for r in self.pending.values()
        ]

    def clear(self) -> None:
        for r in list(self.pending.values()):
            fut: asyncio.Future = r["future"]
            if not fut.done():
                fut.cancel()
        self.pending.clear()


desk = CurtainDesk()

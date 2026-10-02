from __future__ import annotations

import asyncio
import json
from typing import Any

from app import bus
from app.agent.executor import execute
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import TOOL_SPECS, openai_tools
from app.clock import clock
from app.config import get_settings
from app.household import store


class AgentRunner:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self.busy = False

    def reset(self) -> None:
        self.messages = []
        self.busy = False

    async def handle_event(self, title: str, payload: dict[str, Any], source: str) -> None:
        async with self._lock:
            self.busy = True
            try:
                text = self._format_event(title, payload, source)
                self.messages.append({"role": "user", "content": text})
                await bus.emit(
                    "event_in",
                    {"title": title, "source": source, "payload": payload, "clock": clock.iso()},
                )
                await self._loop()
            finally:
                self.busy = False

    def _format_event(self, title: str, payload: dict[str, Any], source: str) -> str:
        return (
            f"EVENT @ {clock.iso()}\n"
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"Payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"{store.render_for_agent()}\n\n"
            "Act through tools only. Write DECISION | RULE | ACTION before each action."
        )

    async def _loop(self) -> None:
        settings = get_settings()
        if settings.llm_provider == "none":
            await bus.emit(
                "agent_error",
                {
                    "message": "No LLM key. Set ANTHROPIC_API_KEY (required for the recording) "
                    "or OPENAI_API_KEY for rehearsal."
                },
            )
            return
        if settings.llm_provider == "anthropic":
            await self._anthropic_loop()
        else:
            await self._openai_loop()

    async def _anthropic_loop(self) -> None:
        from anthropic import Anthropic

        settings = get_settings()
        client = Anthropic(api_key=settings.anthropic_api_key)
        await bus.emit("model_start", {"provider": "anthropic", "model": settings.anthropic_model})

        rounds = 0
        while rounds < 12:
            rounds += 1
            response = await asyncio.to_thread(
                client.messages.create,
                model=settings.anthropic_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_SPECS,
                messages=self.messages,
            )
            assistant_content = []
            tool_uses = []
            text_bits = []
            for block in response.content:
                if block.type == "text":
                    text_bits.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                    await bus.emit("model_text", {"text": block.text})
                    self._maybe_decision(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append(
                        {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                    )
            self.messages.append({"role": "assistant", "content": assistant_content})
            if response.stop_reason != "tool_use":
                break
            results = []
            for block in tool_uses:
                result = await execute(block.name, dict(block.input or {}))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            self.messages.append({"role": "user", "content": results})
        await bus.emit("model_end", {"rounds": rounds})

    async def _openai_loop(self) -> None:
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key)
        await bus.emit("model_start", {"provider": "openai", "model": settings.openai_model})
        oai_messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        oai_messages.extend(self._to_openai_messages())

        rounds = 0
        while rounds < 12:
            rounds += 1
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=settings.openai_model,
                messages=oai_messages,
                tools=openai_tools(),
                tool_choice="auto",
            )
            msg = response.choices[0].message
            oai_messages.append(msg)
            if msg.content:
                await bus.emit("model_text", {"text": msg.content})
                self._maybe_decision(msg.content)
                self.messages.append({"role": "assistant", "content": msg.content})
            if not msg.tool_calls:
                break
            # Keep Anthropic-shaped history in parallel for reset/debug
            tool_blocks = []
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                tool_blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.function.name, "input": args}
                )
                result = await execute(tc.function.name, args)
                oai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            self.messages.append({"role": "assistant", "content": tool_blocks})
        await bus.emit("model_end", {"rounds": rounds})

    def _to_openai_messages(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in self.messages:
            if m["role"] == "user" and isinstance(m["content"], str):
                out.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant" and isinstance(m["content"], str):
                out.append({"role": "assistant", "content": m["content"]})
        return out

    def _maybe_decision(self, text: str) -> None:
        for line in text.splitlines():
            if "DECISION" in line and "|" in line:
                parts = [p.strip() for p in line.split("|")]
                awaitable = {
                    "raw": line,
                    "decision": parts[0] if parts else line,
                    "rule": parts[1] if len(parts) > 1 else "",
                    "action": parts[2] if len(parts) > 2 else "",
                }
                # emit is async; schedule it
                asyncio.create_task(bus.emit("decision", awaitable))


runner = AgentRunner()

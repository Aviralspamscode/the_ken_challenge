from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.clock import clock
from app.config import ROOT, get_settings

RUNTIME = ROOT / "data" / "runtime"
SEED = ROOT / "data" / "household.seed.json"


def _seed() -> dict[str, Any]:
    settings = get_settings()
    return {
        "circle": [
            {
                "name": "Ritika Sinha",
                "role": "owner",
                "language": "en",
                "phone": settings.ritika_phone,
                "cap": None,
                "consented": True,
                "alias": "ritika",
            },
            {
                "name": "Sunita Sinha",
                "role": "full_delegate",
                "language": "hi",
                "phone": settings.sunita_phone,
                "cap": 5000,
                "consented": True,
                "alias": "sunita",
            },
            {
                "name": "Ramesh",
                "role": "approve_each",
                "language": "hi",
                "phone": settings.ramesh_phone,
                "cap": 0,
                "consented": True,
                "alias": "ramesh",
            },
        ],
        "rules": {
            "cod_policy": "buyer_pays_online",
            "quiet_hours": "Ritika in client workshop Saturday 09:00–18:00; do not call her unless third failed attempt / RTO",
            "buyer_blocked": True,
            "refund_cap": 5000,
        },
        "availability": {
            "weekday_afternoon": ["Sunita Sinha"],
            "saturday_morning": ["Sunita Sinha"],
            "saturday_afternoon": ["Sunita Sinha"],
            "saturday_13_00_14_00": [],
            "sunday": ["Ritika Sinha", "Sunita Sinha", "Ramesh"],
        },
        "gaps": [],
        "orders": [],
        "proof_log": [],
        "pending_replies": [],
    }


class HouseholdStore:
    def __init__(self) -> None:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        self.path = RUNTIME / "household.json"
        if not self.path.exists():
            self._write(_seed())

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> dict[str, Any]:
        data = _seed()
        self._write(data)
        return data

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._read())

    def circle(self) -> list[dict[str, Any]]:
        return self._read()["circle"]

    def member_by_phone(self, phone: str) -> dict[str, Any] | None:
        digits = "".join(ch for ch in phone if ch.isdigit())[-10:]
        for m in self.circle():
            if "".join(ch for ch in str(m["phone"]) if ch.isdigit())[-10:] == digits:
                return m
        return None

    def member_by_alias(self, alias: str) -> dict[str, Any] | None:
        alias = alias.lower().strip()
        for m in self.circle():
            if m["alias"] == alias or m["name"].lower().startswith(alias) or m["role"] == alias:
                return m
        if alias in {"buyer", "owner", "maa", "mom", "mother"}:
            key = "ritika" if alias in {"buyer", "owner"} else "sunita"
            return self.member_by_alias(key)
        if alias in {"guard", "watchman"}:
            return self.member_by_alias("ramesh")
        return None

    def in_circle(self, phone: str) -> bool:
        return self.member_by_phone(phone) is not None

    def consented(self, phone: str) -> bool:
        m = self.member_by_phone(phone)
        return bool(m and m.get("consented"))

    def upsert_order(self, order: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        found = False
        for i, existing in enumerate(data["orders"]):
            if existing.get("waybill") == order.get("waybill"):
                existing.update(order)
                data["orders"][i] = existing
                found = True
                break
        if not found:
            data["orders"].append(order)
        self._write(data)
        return order

    def get_order(self, waybill: str) -> dict[str, Any] | None:
        for o in self._read()["orders"]:
            if o.get("waybill") == waybill:
                return o
        return None

    def add_gap(self, gap: dict[str, Any]) -> None:
        data = self._read()
        data["gaps"].append(gap)
        self._write(data)

    def append_proof(self, row: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        row = {"when": clock.iso(), **row}
        data["proof_log"].append(row)
        self._write(data)
        return row

    def watch_reply(self, phone: str, context: str) -> None:
        data = self._read()
        data["pending_replies"].append(
            {"phone": phone, "context": context, "since": clock.iso()}
        )
        self._write(data)

    def clear_reply(self, phone: str) -> None:
        data = self._read()
        digits = "".join(ch for ch in phone if ch.isdigit())[-10:]
        data["pending_replies"] = [
            p
            for p in data["pending_replies"]
            if "".join(ch for ch in str(p["phone"]) if ch.isdigit())[-10:] != digits
        ]
        self._write(data)

    def pending_replies(self) -> list[dict[str, Any]]:
        return self._read().get("pending_replies", [])

    def render_for_agent(self) -> str:
        data = self.snapshot()
        lines = ["HOUSEHOLD SHEET"]
        lines.append("Circle:")
        for m in data["circle"]:
            cap = f"cap ₹{m['cap']}" if m["cap"] is not None else "owner"
            lines.append(
                f"  - {m['name']} | {m['role']} | {m['language']} | {m['phone']} | {cap} | consented={m['consented']}"
            )
        lines.append(f"Rules: {json.dumps(data['rules'], ensure_ascii=False)}")
        lines.append(f"Availability: {json.dumps(data['availability'], ensure_ascii=False)}")
        lines.append(f"Gaps: {json.dumps(data['gaps'], ensure_ascii=False)}")
        lines.append("Open orders:")
        if not data["orders"]:
            lines.append("  (none)")
        for o in data["orders"]:
            lines.append("  - " + json.dumps(o, ensure_ascii=False))
        lines.append(f"Pending reply-watches: {json.dumps(data['pending_replies'], ensure_ascii=False)}")
        return "\n".join(lines)


store = HouseholdStore()

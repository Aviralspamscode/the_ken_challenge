from __future__ import annotations

from typing import Any

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "household_sheet",
        "description": "Read or write the household sheet: circle, rules, availability, orders, proof log.",
        "input_schema": {
            "type": "object",
            "properties": {
                "op": {
                    "type": "string",
                    "enum": ["read", "upsert_order", "add_gap", "append_proof"],
                },
                "order": {"type": "object", "description": "Order fields when op=upsert_order"},
                "gap": {"type": "object", "description": "Availability gap when op=add_gap"},
                "proof": {
                    "type": "object",
                    "description": "Proof row: decision, rule, action, who, connector, waybills",
                },
            },
            "required": ["op"],
        },
    },
    {
        "name": "track_shipment",
        "description": "GET Delhivery /api/v1/packages/json/?waybill= — read status, status code, ETA.",
        "input_schema": {
            "type": "object",
            "properties": {"waybill": {"type": "string"}},
            "required": ["waybill"],
        },
    },
    {
        "name": "update_shipment",
        "description": (
            "Delhivery write. action=edit → POST /api/p/edit (name, phone, pt, cod) only before Dispatched. "
            "action=defer → POST /api/p/update DEFER_DLV (max 6 days). "
            "action=reattempt → POST /api/p/update RE-ATTEMPT. "
            "action=pickup_reschedule → reverse pickup reschedule with evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["edit", "defer", "reattempt", "pickup_reschedule"],
                },
                "waybill": {"type": "string"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "pt": {"type": "string", "description": "Pre-paid or COD"},
                "cod": {"type": "number"},
                "action_data": {"type": "object"},
                "evidence": {"type": "string", "description": "Call transcript for R9 reschedule"},
            },
            "required": ["action", "waybill"],
        },
    },
    {
        "name": "create_return_pickup",
        "description": "POST Delhivery /api/cmu/create.json with payment_mode=Pickup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "waybill": {"type": "string"},
                "item": {"type": "string"},
                "pickup_date": {"type": "string", "description": "YYYY-MM-DD, prefer Sunday when everyone is home"},
                "address": {"type": "string"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "value": {"type": "number"},
            },
            "required": ["item", "pickup_date", "name", "phone"],
        },
    },
    {
        "name": "call_person",
        "description": "Live Gnani outbound Hindi call. POST /v1/agents/{botId}/trigger_call then poll stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string"},
                "name": {"type": "string"},
                "reason": {"type": "string", "description": "Why you are calling — used as clientReferenceId context"},
                "script_hint": {"type": "string"},
            },
            "required": ["phone", "name", "reason"],
        },
    },
    {
        "name": "transcribe_voice_note",
        "description": "Live Gnani Vachana STT POST /stt/v3. Use when a voice note media id is provided.",
        "input_schema": {
            "type": "object",
            "properties": {
                "media_id": {"type": "string"},
                "audio_path": {"type": "string"},
                "language_code": {"type": "string", "default": "hi-IN"},
            },
        },
    },
    {
        "name": "collect_cod",
        "description": "Pine Labs POST /api/pay/v1/paymentlink so the buyer pays COD remotely.",
        "input_schema": {
            "type": "object",
            "properties": {
                "waybill": {"type": "string"},
                "amount_rupees": {"type": "number"},
                "description": {"type": "string"},
                "buyer_phone": {"type": "string"},
                "reference": {"type": "string"},
            },
            "required": ["waybill", "amount_rupees", "buyer_phone"],
        },
    },
    {
        "name": "refund_on_pickup",
        "description": "Pine Labs POST /api/pay/v1/refunds/{order_id}. Only after a Picked Up scan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "waybill": {"type": "string"},
                "order_id": {"type": "string"},
                "amount_rupees": {"type": "number"},
                "reference": {"type": "string"},
            },
            "required": ["waybill", "amount_rupees"],
        },
    },
    {
        "name": "message",
        "description": "Send a WhatsApp text to a circle member. Hindi speakers get Devanagari.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Phone, alias (ritika/sunita/ramesh), or role (buyer/owner)",
                },
                "text": {"type": "string"},
                "watch_for_reply": {
                    "type": "boolean",
                    "description": "If true, a 10-minute no-reply clock tick will be raised later (R3)",
                },
            },
            "required": ["to", "text"],
        },
    },
]


def openai_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOL_SPECS
    ]

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.clock import IST, clock
from app.config import get_settings
from app.household import store


def _phones() -> dict[str, str]:
    s = get_settings()
    return {"ritika": s.ritika_phone, "sunita": s.sunita_phone, "ramesh": s.ramesh_phone}


def catalog() -> list[dict[str, Any]]:
    return [
        {"id": "d1_d2", "label": "D1+D2 · 09:05 both parcels arrive", "clock": "2026-10-03T09:05"},
        {"id": "d3", "label": "D3 · 09:21 Ritika paid the COD link", "clock": "2026-10-03T09:21"},
        {"id": "d4", "label": "D4 · 09:34 Sunita voice note (mandir)", "clock": "2026-10-03T09:34"},
        {"id": "d5", "label": "D5 · 12:10 A & B Dispatched", "clock": "2026-10-03T12:10"},
        {"id": "d6", "label": "D6 · 12:20 no reply (10 min)", "clock": "2026-10-03T12:20"},
        {"id": "d7", "label": "D7 · 12:58 A & B Delivered", "clock": "2026-10-03T12:58"},
        {"id": "d8", "label": "D8 · 18:30 Ritika asks for shoe return", "clock": "2026-10-03T18:30"},
        {"id": "d9", "label": "D9 · Sun 11:40 pickup 'not available'", "clock": "2026-10-04T11:40"},
        {"id": "d11", "label": "D11 · Sun 15:10 Picked Up", "clock": "2026-10-04T15:10"},
    ]


def build(scenario_id: str) -> dict[str, Any]:
    p = _phones()
    builders = {
        "d1_d2": _morning,
        "d3": _paid,
        "d4": _voice,
        "d5": _dispatched,
        "d6": _no_reply,
        "d7": _delivered,
        "d8": _return_ask,
        "d9": _pickup_fail,
        "d11": _picked_up,
    }
    if scenario_id not in builders:
        raise KeyError(scenario_id)
    return builders[scenario_id](p)


def apply_clock(stamp: str) -> None:
    clock.set(datetime.fromisoformat(stamp).replace(tzinfo=IST))


def _morning(p: dict[str, str]) -> dict[str, Any]:
    store.upsert_order(
        {
            "waybill": "1234567890123",
            "item": "Headphones",
            "value": 3499,
            "pt": "Pre-paid",
            "cod": 0,
            "otp_protected": True,
            "status": "Pending",
            "status_type": "UD",
            "location": "Patna DC",
            "consignee": "Ritika Sinha",
            "phone": p["ritika"],
        }
    )
    store.upsert_order(
        {
            "waybill": "1234567890456",
            "item": "Kurta",
            "value": 899,
            "pt": "COD",
            "cod": 899,
            "otp_protected": False,
            "status": "Pending",
            "status_type": "UD",
            "location": "Patna DC",
            "consignee": "Ritika Sinha",
            "phone": p["ritika"],
        }
    )
    return {
        "title": "Two Delhivery push scans at Patna DC",
        "source": "webhook → Delhivery push scan (pasted by curtain in documented shape)",
        "payload": {
            "scans": [
                {
                    "Shipment": {
                        "AWB": "1234567890123",
                        "OrderType": "Pre-paid",
                        "CODAmount": 0,
                        "Consignee": {"Name": "Ritika Sinha", "Phone": p["ritika"]},
                        "Status": {
                            "Status": "Pending",
                            "StatusType": "UD",
                            "StatusDateTime": "2026-10-03T09:05:00+05:30",
                            "Instructions": "Pending at Patna DC",
                        },
                        "ReferenceNo": "Headphones",
                        "DeclaredValue": 3499,
                        "OTPProtected": True,
                    }
                },
                {
                    "Shipment": {
                        "AWB": "1234567890456",
                        "OrderType": "COD",
                        "CODAmount": 899,
                        "Consignee": {"Name": "Ritika Sinha", "Phone": p["ritika"]},
                        "Status": {
                            "Status": "Pending",
                            "StatusType": "UD",
                            "StatusDateTime": "2026-10-03T09:05:00+05:30",
                            "Instructions": "Pending at Patna DC",
                        },
                        "ReferenceNo": "Kurta",
                        "DeclaredValue": 899,
                    }
                },
            ]
        },
    }


def _paid(p: dict[str, str]) -> dict[str, Any]:
    return {
        "title": "Pine Labs payment link PROCESSED",
        "source": "webhook → Pine Labs UAT (doc-shaped)",
        "payload": {
            "event": "PAYMENT_LINK",
            "status": "PROCESSED",
            "merchant_payment_link_reference": "gp-890456",
            "waybill": "1234567890456",
            "amount": {"value": 89900, "currency": "INR"},
            "customer": {"mobile_number": p["ritika"]},
        },
    }


def _voice(p: dict[str, str]) -> dict[str, Any]:
    return {
        "title": "Sunita sent a WhatsApp voice note",
        "source": "WhatsApp → real voice note, transcribed live by Gnani /stt/v3",
        "payload": {
            "from": p["sunita"],
            "name": "Sunita Sinha",
            "type": "audio",
            "transcript": "बेटा, एक से दो बजे मंदिर जाऊँगी",
            "transcript_roman": "Beta, ek se do baje mandir jaungi",
            "note": "If you recorded a real voice note, prefer /operator/voice so STT runs live. This inject uses the expected transcript only when you need to keep moving.",
        },
    }


def _dispatched(p: dict[str, str]) -> dict[str, Any]:
    for wbn in ("1234567890123", "1234567890456"):
        store.upsert_order({"waybill": wbn, "status": "Dispatched", "status_type": "UD"})
    return {
        "title": "A and B Dispatched",
        "source": "webhook → Delhivery push scan",
        "payload": {
            "scans": [
                {
                    "Shipment": {
                        "AWB": "1234567890123",
                        "Status": {
                            "Status": "Dispatched",
                            "StatusType": "UD",
                            "StatusDateTime": "2026-10-03T12:10:00+05:30",
                        },
                    }
                },
                {
                    "Shipment": {
                        "AWB": "1234567890456",
                        "Status": {
                            "Status": "Dispatched",
                            "StatusType": "UD",
                            "StatusDateTime": "2026-10-03T12:10:00+05:30",
                        },
                    }
                },
            ]
        },
    }


def _no_reply(p: dict[str, str]) -> dict[str, Any]:
    return {
        "title": "Clock: 10 minutes, no reply from Sunita",
        "source": "clock → system time",
        "payload": {
            "elapsed_minutes": 10,
            "watched": store.pending_replies() or [{"phone": p["sunita"], "context": "Dispatched warning"}],
            "hint": "R3 — call the receiver, not the buyer.",
        },
    }


def _delivered(p: dict[str, str]) -> dict[str, Any]:
    for wbn in ("1234567890123", "1234567890456"):
        store.upsert_order({"waybill": wbn, "status": "Delivered", "status_type": "DL", "delivered_to": "Sunita Sinha"})
    return {
        "title": "A and B Delivered",
        "source": "webhook → Delhivery push scan",
        "payload": {
            "scans": [
                {
                    "Shipment": {
                        "AWB": "1234567890123",
                        "Status": {
                            "Status": "Delivered",
                            "StatusType": "DL",
                            "StatusDateTime": "2026-10-03T12:58:00+05:30",
                        },
                    }
                },
                {
                    "Shipment": {
                        "AWB": "1234567890456",
                        "Status": {
                            "Status": "Delivered",
                            "StatusType": "DL",
                            "StatusDateTime": "2026-10-03T12:58:00+05:30",
                        },
                    }
                },
            ]
        },
    }


def _return_ask(p: dict[str, str]) -> dict[str, Any]:
    return {
        "title": "Ritika WhatsApp: shoes are the wrong size",
        "source": "WhatsApp → Ritika (teammate on her phone)",
        "payload": {
            "from": p["ritika"],
            "name": "Ritika Sinha",
            "type": "text",
            "text": "Shoes size galat, return karna hai",
            "order": {
                "item": "Shoes",
                "value": 2199,
                "original_waybill": "1234567890777",
            },
        },
    }


def _pickup_fail(p: dict[str, str]) -> dict[str, Any]:
    store.upsert_order(
        {
            "waybill": "R1234567890999",
            "item": "Shoes",
            "value": 2199,
            "status": "customer_not_available",
            "kind": "return_pickup",
        }
    )
    return {
        "title": "Return pickup marked customer not available",
        "source": "webhook → Delhivery push scan",
        "payload": {
            "Shipment": {
                "AWB": "R1234567890999",
                "Status": {
                    "Status": "Customer not available",
                    "StatusType": "UD",
                    "StatusDateTime": "2026-10-04T11:40:00+05:30",
                    "Instructions": "Pickup attempted — customer not available",
                },
                "ReferenceNo": "Shoes",
                "DeclaredValue": 2199,
            }
        },
    }


def _picked_up(p: dict[str, str]) -> dict[str, Any]:
    store.upsert_order(
        {
            "waybill": "R1234567890999",
            "item": "Shoes",
            "value": 2199,
            "status": "Picked Up",
            "kind": "return_pickup",
        }
    )
    return {
        "title": "Return pickup Picked Up",
        "source": "webhook → Delhivery push scan",
        "payload": {
            "Shipment": {
                "AWB": "R1234567890999",
                "Status": {
                    "Status": "Picked Up",
                    "StatusType": "PU",
                    "StatusDateTime": "2026-10-04T15:10:00+05:30",
                },
                "ReferenceNo": "Shoes",
                "DeclaredValue": 2199,
            }
        },
    }

from __future__ import annotations

from typing import Any

import httpx

from app import bus
from app.config import get_settings
from app.connectors.curtain import desk
from app.household import store


SAMPLES = {
    "track": {
        "ShipmentData": [
            {
                "Shipment": {
                    "AWB": "1234567890123",
                    "Status": {
                        "Status": "Pending",
                        "StatusType": "UD",
                        "StatusDateTime": "2026-10-03T09:05:00",
                        "Instructions": "Pending at Patna DC",
                    },
                }
            }
        ]
    },
    "edit": {"request_id": "UPL-EDIT-20261003-001", "message": "Edit request accepted"},
    "ndr": {"message": "Request accepted", "request_id": "UPL202610031146001"},
    "create_return": {
        "success": True,
        "packages": [{"waybill": "R1234567890999", "status": "Success", "remarks": "Pickup booked"}],
    },
}


def _live() -> bool:
    s = get_settings()
    return bool(s.delhivery_live and s.delhivery_api_token)


async def _http(method: str, path: str, **kwargs) -> dict[str, Any]:
    s = get_settings()
    url = s.delhivery_base.rstrip("/") + path
    headers = {"Authorization": f"Token {s.delhivery_api_token}", "Content-Type": "application/json"}
    await bus.emit("http_request", {"partner": "delhivery", "method": method, "url": url, **kwargs})
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, url, headers=headers, **kwargs)
        data = resp.json() if "json" in resp.headers.get("content-type", "") else {"raw": resp.text}
    await bus.emit("http_response", {"partner": "delhivery", "status": resp.status_code, "body": data, "url": url})
    return data


async def track(waybill: str) -> dict[str, Any]:
    local = store.get_order(waybill) or {"waybill": waybill}
    request = {"waybill": waybill}
    if _live():
        return await _http("GET", f"/api/v1/packages/json/?waybill={waybill}")
    sample = {
        "ShipmentData": [
            {
                "Shipment": {
                    "AWB": waybill,
                    "Status": {
                        "Status": local.get("status", "Pending"),
                        "StatusType": local.get("status_type", "UD"),
                        "StatusDateTime": local.get("status_at", "2026-10-03T09:05:00"),
                    },
                    "OrderType": local.get("pt", "Pre-paid"),
                    "CODAmount": local.get("cod", 0),
                }
            }
        ]
    }
    return await desk.ask(
        "delhivery",
        "GET",
        f"/api/v1/packages/json/?waybill={waybill}",
        request,
        sample=sample,
    )


async def edit(waybill: str, fields: dict[str, Any]) -> dict[str, Any]:
    order = store.get_order(waybill)
    if order and str(order.get("status", "")).lower() == "dispatched":
        return {
            "error": "edit_blocked",
            "message": "Hard rule: edits are impossible after Dispatched (R2).",
        }
    if fields.get("phone") and not store.consented(str(fields["phone"])):
        return {
            "error": "outside_circle",
            "message": "Hard rule R1: never re-route to anyone outside the consented circle.",
        }
    body = {"waybill": waybill, **{k: v for k, v in fields.items() if v is not None}}
    if _live():
        return await _http("POST", "/api/p/edit", json=body)
    return await desk.ask("delhivery", "POST", "/api/p/edit", body, sample=SAMPLES["edit"])


async def ndr(waybill: str, act: str, action_data: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {"data": [{"waybill": waybill, "act": act, "action_data": action_data or {}}]}
    if _live():
        return await _http("POST", "/api/p/update", json=body)
    return await desk.ask("delhivery", "POST", "/api/p/update", body, sample=SAMPLES["ndr"])


async def create_return(
    *,
    item: str,
    pickup_date: str,
    name: str,
    phone: str,
    value: float = 0,
    waybill: str | None = None,
    address: str = "Kankarbagh, Patna",
) -> dict[str, Any]:
    if not store.consented(phone):
        return {"error": "outside_circle", "message": "Hard rule R1: pickup contact must be in the circle."}
    s = get_settings()
    shipment = {
        "name": name,
        "phone": phone,
        "address": address,
        "payment_mode": "Pickup",
        "products_desc": item,
        "shipment_width": "10",
        "shipment_height": "10",
        "weight": "500",
        "pickup_date": pickup_date,
        "total_amount": value,
    }
    if waybill:
        shipment["order"] = waybill
    body = {
        "format": "json",
        "data": {
            "shipments": [shipment],
            "pickup_location": {"name": s.delhivery_pickup_location or "GharPass Patna"},
        },
    }
    if _live():
        return await _http("POST", "/api/cmu/create.json", json=body)
    return await desk.ask(
        "delhivery",
        "POST",
        "/api/cmu/create.json",
        body,
        sample=SAMPLES["create_return"],
    )

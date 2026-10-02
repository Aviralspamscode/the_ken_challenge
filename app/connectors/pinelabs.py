from __future__ import annotations

from typing import Any

import httpx

from app import bus
from app.config import get_settings
from app.connectors.curtain import desk
from app.household import store


def _live() -> bool:
    s = get_settings()
    return bool(s.pinelabs_live and s.pinelabs_client_id and s.pinelabs_client_secret)


async def _token() -> str:
    s = get_settings()
    url = f"{s.pinelabs_base}/api/auth/v1/token"
    body = {
        "client_id": s.pinelabs_client_id,
        "client_secret": s.pinelabs_client_secret,
        "grant_type": "client_credentials",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()["access_token"]


async def create_payment_link(
    *,
    waybill: str,
    amount_rupees: float,
    buyer_phone: str,
    description: str = "",
    reference: str | None = None,
) -> dict[str, Any]:
    paise = int(round(amount_rupees * 100))
    ref = reference or f"gp-{waybill[-6:]}"
    body = {
        "merchant_payment_link_reference": ref,
        "amount": {"value": paise, "currency": "INR"},
        "description": description or f"COD for waybill {waybill}",
        "customer": {"mobile_number": "".join(ch for ch in buyer_phone if ch.isdigit())[-10:]},
    }
    sample = {
        "payment_link_id": "pl_gp_demo_899",
        "merchant_payment_link_reference": ref,
        "status": "CREATED",
        "payment_link": "https://pluraluat.v2.pinepg.in/pay/pl_gp_demo_899",
        "amount": body["amount"],
    }
    if _live():
        s = get_settings()
        token = await _token()
        url = f"{s.pinelabs_base}/api/pay/v1/paymentlink"
        await bus.emit("http_request", {"partner": "pine_labs", "method": "POST", "url": url, "body": body})
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
            data = resp.json()
        await bus.emit("http_response", {"partner": "pine_labs", "status": resp.status_code, "body": data})
        return data
    return await desk.ask("pine_labs", "POST", "/api/pay/v1/paymentlink", body, sample=sample)


async def refund(
    *,
    waybill: str,
    amount_rupees: float,
    order_id: str | None = None,
    reference: str | None = None,
) -> dict[str, Any]:
    order = store.get_order(waybill) or {}
    status = str(order.get("status", "")).lower().replace(" ", "_")
    if "picked" not in status and status not in {"picked_up", "pickup_done"}:
        return {
            "error": "no_pickup_scan",
            "message": "Hard rule R10 / R2: never refund without a Delhivery Picked Up scan.",
        }
    if amount_rupees > 5000 and not order.get("warehouse_qc"):
        return {
            "error": "qc_required",
            "message": "Hard rule R10: value > ₹5,000 — wait for warehouse QC.",
        }
    paise = int(round(amount_rupees * 100))
    oid = order_id or order.get("pine_order_id") or f"ord-{waybill[-6:]}"
    body = {
        "merchant_order_reference": reference or f"gp-R-{waybill[-6:]}",
        "order_amount": {"value": paise, "currency": "INR"},
    }
    sample = {
        "refund_id": "rfnd_gp_2199",
        "order_id": oid,
        "status": "PROCESSED",
        "order_amount": body["order_amount"],
    }
    if _live():
        s = get_settings()
        token = await _token()
        url = f"{s.pinelabs_base}/api/pay/v1/refunds/{oid}"
        await bus.emit("http_request", {"partner": "pine_labs", "method": "POST", "url": url, "body": body})
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
            data = resp.json()
        await bus.emit("http_response", {"partner": "pine_labs", "status": resp.status_code, "body": data})
        return data
    return await desk.ask("pine_labs", "POST", f"/api/pay/v1/refunds/{oid}", body, sample=sample)

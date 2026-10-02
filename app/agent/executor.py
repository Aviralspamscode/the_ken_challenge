from __future__ import annotations

from typing import Any

from app import bus
from app.connectors import delhivery, gnani, pinelabs, sheets, whatsapp
from app.household import store


async def execute(name: str, args: dict[str, Any]) -> Any:
    await bus.emit("tool_call", {"name": name, "args": args})
    try:
        result = await _dispatch(name, args)
    except Exception as exc:  # noqa: BLE001 — surface to the model, keep the recording alive
        result = {"error": type(exc).__name__, "message": str(exc)}
    await bus.emit("tool_result", {"name": name, "result": result})
    return result


async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "household_sheet":
        return await _sheet(args)
    if name == "track_shipment":
        return await delhivery.track(args["waybill"])
    if name == "update_shipment":
        return await _update(args)
    if name == "create_return_pickup":
        return await delhivery.create_return(
            item=args["item"],
            pickup_date=args["pickup_date"],
            name=args["name"],
            phone=args["phone"],
            value=float(args.get("value") or 0),
            waybill=args.get("waybill"),
            address=args.get("address") or "Kankarbagh, Patna",
        )
    if name == "call_person":
        return await gnani.place_call_and_wait(args["phone"], args["name"], args["reason"])
    if name == "transcribe_voice_note":
        if args.get("audio_path"):
            return await gnani.transcribe_file(args["audio_path"], args.get("language_code") or "hi-IN")
        if args.get("media_id"):
            audio, filename = await whatsapp.download_media(args["media_id"])
            return await gnani.transcribe(audio, filename, args.get("language_code") or "hi-IN")
        return {"error": "need media_id or audio_path"}
    if name == "collect_cod":
        return await pinelabs.create_payment_link(
            waybill=args["waybill"],
            amount_rupees=float(args["amount_rupees"]),
            buyer_phone=args["buyer_phone"],
            description=args.get("description") or "",
            reference=args.get("reference"),
        )
    if name == "refund_on_pickup":
        return await pinelabs.refund(
            waybill=args["waybill"],
            amount_rupees=float(args["amount_rupees"]),
            order_id=args.get("order_id"),
            reference=args.get("reference"),
        )
    if name == "message":
        result = await whatsapp.send_text(args["to"], args["text"])
        if args.get("watch_for_reply"):
            store.watch_reply(result["to"], args["text"][:80])
        return result
    return {"error": f"unknown tool {name}"}


async def _sheet(args: dict[str, Any]) -> Any:
    op = args["op"]
    if op == "read":
        return store.snapshot()
    if op == "upsert_order":
        return store.upsert_order(args.get("order") or {})
    if op == "add_gap":
        store.add_gap(args.get("gap") or {})
        return {"ok": True}
    if op == "append_proof":
        return await sheets.sync_proof(args.get("proof") or {})
    return {"error": f"unknown op {op}"}


async def _update(args: dict[str, Any]) -> Any:
    action = args["action"]
    waybill = args["waybill"]
    if action == "edit":
        result = await delhivery.edit(
            waybill,
            {
                "name": args.get("name"),
                "phone": args.get("phone"),
                "pt": args.get("pt"),
                "cod": args.get("cod"),
            },
        )
        if "error" not in result:
            patch = {"waybill": waybill}
            if args.get("name"):
                patch["consignee"] = args["name"]
            if args.get("phone"):
                patch["phone"] = args["phone"]
            if args.get("pt"):
                patch["pt"] = args["pt"]
            if args.get("cod") is not None:
                patch["cod"] = args["cod"]
            store.upsert_order(patch)
        return result
    act = {
        "defer": "DEFER_DLV",
        "reattempt": "RE-ATTEMPT",
        "pickup_reschedule": "PICKUP_RESCHEDULE",
    }[action]
    action_data = dict(args.get("action_data") or {})
    if args.get("evidence"):
        action_data["evidence"] = args["evidence"]
    return await delhivery.ndr(waybill, act, action_data)

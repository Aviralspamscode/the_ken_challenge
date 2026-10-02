from __future__ import annotations

import json
from typing import Any

from app import bus
from app.config import ROOT, get_settings
from app.household import store


def _client():
    s = get_settings()
    if not s.google_service_account_file or not s.google_sheet_id:
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    path = s.google_service_account_file
    if not path.startswith("/") and ":" not in path:
        path = str(ROOT / path)
    creds = service_account.Credentials.from_service_account_file(
        path,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


async def sync_proof(row: dict[str, Any]) -> dict[str, Any]:
    """Always persist locally; also append to Google Sheets when configured."""
    saved = store.append_proof(row)
    s = get_settings()
    if not s.google_service_account_file or not s.google_sheet_id:
        await bus.emit(
            "sheets_local",
            {"note": "Google Sheets not configured — proof row written to local household.json", "row": saved},
        )
        return {"channel": "local", "row": saved}
    try:
        svc = _client()
        values = [[
            saved.get("when", ""),
            saved.get("decision", ""),
            saved.get("rule", ""),
            saved.get("action", ""),
            saved.get("who", ""),
            saved.get("connector", ""),
            json.dumps(saved.get("waybills", []), ensure_ascii=False),
        ]]
        svc.spreadsheets().values().append(
            spreadsheetId=s.google_sheet_id,
            range="Proof!A:G",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()
        await bus.emit("sheets_remote", {"row": saved})
        return {"channel": "sheets", "row": saved}
    except Exception as exc:  # noqa: BLE001 — recording must not die on sheet errors
        await bus.emit("sheets_error", {"error": str(exc), "row": saved})
        return {"channel": "local", "error": str(exc), "row": saved}


async def bootstrap_sheet() -> dict[str, Any]:
    s = get_settings()
    if not s.google_service_account_file or not s.google_sheet_id:
        return {"ok": False, "reason": "GOOGLE_SERVICE_ACCOUNT_FILE / GOOGLE_SHEET_ID not set"}
    svc = _client()
    data = store.snapshot()
    circle_rows = [["name", "role", "language", "phone", "cap", "consented"]]
    for m in data["circle"]:
        circle_rows.append([m["name"], m["role"], m["language"], m["phone"], m.get("cap") or "", m["consented"]])
    svc.spreadsheets().values().update(
        spreadsheetId=s.google_sheet_id,
        range="Circle!A1",
        valueInputOption="RAW",
        body={"values": circle_rows},
    ).execute()
    svc.spreadsheets().values().update(
        spreadsheetId=s.google_sheet_id,
        range="Proof!A1",
        valueInputOption="RAW",
        body={"values": [["when", "decision", "rule", "action", "who", "connector", "waybills"]]},
    ).execute()
    return {"ok": True}

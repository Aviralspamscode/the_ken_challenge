from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:  # Windows without tzdata
    IST = timezone(timedelta(hours=5, minutes=30))

RECORDING_START = datetime(2026, 10, 3, 9, 0, tzinfo=IST)


class SimClock:
    """A recording clock. Starts Saturday 3 Oct 2026 09:00 IST and can jump."""

    def __init__(self) -> None:
        self._now = RECORDING_START

    def now(self) -> datetime:
        return self._now

    def iso(self) -> str:
        return self._now.strftime("Sat %Y-%m-%d %H:%M IST") if self._now.weekday() == 5 else self._now.strftime("%a %Y-%m-%d %H:%M IST")

    def label(self) -> str:
        return self._now.strftime("%a %d %b %Y · %H:%M IST")

    def set(self, when: datetime) -> datetime:
        if when.tzinfo is None:
            when = when.replace(tzinfo=IST)
        self._now = when.astimezone(IST)
        return self._now

    def advance(self, minutes: int) -> datetime:
        self._now = self._now + timedelta(minutes=minutes)
        return self._now

    def reset(self) -> datetime:
        self._now = RECORDING_START
        return self._now


clock = SimClock()

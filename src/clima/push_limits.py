"""Shared daily Web Push rate-limit keys and local-day expiry helpers."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

MAX_DAILY_PUSHES = 3


def pushSentKey(userId: int, day: date) -> str:
    return f"push_sent:{userId}:{day.isoformat()}"


def wardrobeHintSentKey(userId: int, day: date) -> str:
    return f"wardrobe_hint_sent:{userId}:{day.isoformat()}"


def pushCountKey(userId: int, day: date) -> str:
    return f"push_count:{userId}:{day.isoformat()}"


def localDate(now: datetime, timeZone: str) -> date:
    return now.astimezone(ZoneInfo(timeZone)).date()


def secondsUntilLocalMidnight(now: datetime, timeZone: str) -> float:
    zone = ZoneInfo(timeZone)
    localNow = now.astimezone(zone)
    nextMidnight = datetime.combine(
        localNow.date() + timedelta(days=1), time.min, zone
    )
    return max(
        1,
        (
            nextMidnight.astimezone(timezone.utc)
            - localNow.astimezone(timezone.utc)
        ).total_seconds(),
    )

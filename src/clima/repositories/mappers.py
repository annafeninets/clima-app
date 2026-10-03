"""SQLite row-to-domain conversion shared by repositories."""

from datetime import datetime, time, timezone
import json
import sqlite3

from clima.models.entities import Item, Preferences, Settings, User
from clima.models.enums import ItemPart, Season, Theme
from clima.models.value_objects import PushSubscription


def datetime_from_db(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


def user_from_row(row: sqlite3.Row) -> User:
    preferences = Preferences(**json.loads(row["preferences"]))
    settings_data = json.loads(row["settings"])
    subscription = settings_data.get("pushSubscription")
    settings = Settings(
        theme=Theme(settings_data.get("theme", "LIGHT")),
        notificationsEnabled=settings_data.get("notificationsEnabled", False),
        notificationTime=time.fromisoformat(settings_data.get("notificationTime", "07:00")),
        timeZone=settings_data.get("timeZone", "UTC"),
        pushSubscription=PushSubscription(**subscription) if subscription else None,
    )
    return User(
        id=row["id"], createdAt=datetime_from_db(row["created_at"]),
        email=row["email"], phone=row["phone"], passwordHash=row["password_hash"],
        location=row["location"], preferences=preferences, settings=settings,
    )


def item_from_row(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"], userId=row["user_id"], createdAt=datetime_from_db(row["created_at"]),
        photo=row["photo"], type=row["type"], color=row["color"],
        seasons=[Season(value) for value in json.loads(row["seasons"])],
        minTemperature=row["min_temperature"], maxTemperature=row["max_temperature"],
        part=ItemPart(row["part"]), dressCode=row["dress_code"], style=row["style"],
        silhouette=row["silhouette"], material=row["material"],
        inLaundry=bool(row["in_laundry"]), deleted=bool(row["deleted"]),
    )

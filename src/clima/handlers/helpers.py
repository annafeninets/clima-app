from base64 import b64decode
from datetime import date, time
import binascii

from clima.errors import ValidationError
from clima.models.entities import Item, Preferences
from clima.models.enums import ItemPart, Season
from clima.models.value_objects import OutfitFilter, PushSubscription


def parse_photo(value) -> bytes:
    if not isinstance(value, str):
        raise ValidationError("Фото должно быть передано в формате base64")
    if value.startswith("data:") and "," in value:
        value = value.split(",", 1)[1]
    try:
        return b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValidationError("Некорректное base64-фото") from error


def item_from_data(data: dict, userId: int, existing: Item | None = None) -> Item:
    base = existing or Item(userId=userId)
    values = _item_values(data)
    try:
        seasons = [Season(str(value).upper()) for value in values.get(
            "seasons", [s.value for s in base.seasons]
        )]
        part = ItemPart(str(values.get("part", base.part.value)).upper())
        minimum = int(values.get("minTemperature", base.minTemperature))
        maximum = int(values.get("maxTemperature", base.maxTemperature))
    except (ValueError, TypeError) as error:
        raise ValidationError("Некорректные характеристики вещи") from error
    return Item(
        id=base.id, userId=userId, createdAt=base.createdAt,
        photo=base.photo, type=str(values.get("type", base.type)),
        color=str(values.get("color", base.color)), seasons=seasons,
        minTemperature=minimum, maxTemperature=maximum, part=part,
        dressCode=str(values.get("dressCode", base.dressCode)),
        style=str(values.get("style", base.style)),
        silhouette=str(values.get("silhouette", base.silhouette)),
        material=str(values.get("material", base.material)),
        inLaundry=base.inLaundry, deleted=base.deleted,
    )


def preferences_from_data(data: dict) -> Preferences:
    return Preferences(
        style=str(data.get("style", "")), colors=str(data.get("colors", "")),
        sizes=str(data.get("sizes", "")), bodyFeatures=str(data.get("bodyFeatures", "")),
    )


def outfit_filter(query: dict[str, str], location: str = "") -> OutfitFilter:
    raw_date = query.get("date", date.today().isoformat())
    place = query.get("place", query.get("location", location)).strip()
    try:
        selected_date = date.fromisoformat(raw_date)
    except ValueError as error:
        raise ValidationError("Дата должна быть в формате ГГГГ-ММ-ДД") from error
    raw_temperature = query.get("temperature")
    try:
        temperature = int(raw_temperature) if raw_temperature not in (None, "") else None
    except (ValueError, TypeError) as error:
        raise ValidationError("Температура должна быть целым числом") from error
    raw_season = query.get("season")
    try:
        season = Season(raw_season.upper()) if raw_season else None
    except (AttributeError, ValueError) as error:
        raise ValidationError("Некорректный сезон") from error
    return OutfitFilter(
        selected_date, place, query.get("occasion", "everyday"), temperature, season
    )


def parse_time(value) -> time:
    if not isinstance(value, str):
        raise ValidationError("Время должно иметь формат ЧЧ:ММ")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ValidationError("Время должно иметь формат ЧЧ:ММ") from error
    if parsed.second or parsed.microsecond or parsed.tzinfo:
        raise ValidationError("Укажите время в формате ЧЧ:ММ")
    return parsed


def push_subscription(data: dict) -> PushSubscription:
    keys = data.get("keys") or {}
    return PushSubscription(
        endpoint=str(data.get("endpoint", "")),
        p256dh=str(keys.get("p256dh", data.get("p256dh", ""))),
        auth=str(keys.get("auth", data.get("auth", ""))),
    )


def _item_values(data: dict) -> dict:
    aliases = {
        "min_temperature": "minTemperature",
        "max_temperature": "maxTemperature",
        "dress_code": "dressCode",
    }
    values = dict(data)
    for source, target in aliases.items():
        if target not in values and source in values:
            values[target] = values[source]
    return values

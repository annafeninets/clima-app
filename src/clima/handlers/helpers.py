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
        photo=base.photo, type=_string_value(values, "type", base.type),
        color=_string_value(values, "color", base.color), seasons=seasons,
        minTemperature=minimum, maxTemperature=maximum, part=part,
        dressCode=_string_value(values, "dressCode", base.dressCode),
        style=_string_value(values, "style", base.style),
        silhouette=_string_value(values, "silhouette", base.silhouette),
        material=_string_value(values, "material", base.material),
        inLaundry=base.inLaundry, deleted=base.deleted,
    )


def _string_value(data: dict, key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValidationError(f"Поле {key} должно быть строкой")
    return value


def preferences_from_data(data: dict) -> Preferences:
    values = {
        "style": data.get("style", ""),
        "colors": data.get("colors", ""),
        "sizes": data.get("sizes", ""),
        "bodyFeatures": data.get("bodyFeatures", ""),
    }
    for name, value in values.items():
        if not isinstance(value, str):
            raise ValidationError(f"Поле {name} должно быть строкой")
        if len(value) > 500:
            raise ValidationError(f"Поле {name} не должно превышать 500 символов")
    return Preferences(**values)


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
    if not isinstance(keys, dict):
        raise ValidationError("Ключи push-подписки должны быть объектом")
    endpoint = data.get("endpoint", "")
    p256dh = keys.get("p256dh", data.get("p256dh", ""))
    auth = keys.get("auth", data.get("auth", ""))
    if not all(isinstance(value, str) for value in (endpoint, p256dh, auth)):
        raise ValidationError("Поля push-подписки должны быть строками")
    return PushSubscription(
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
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

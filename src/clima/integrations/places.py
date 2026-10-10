"""Нормализация ответов геокодеров в единый формат места.

Гибрид: локальный датасет на клиенте для мгновенного автокомплита,
Open-Meteo и Nominatim (OSM) на сервере как fallback без API-ключа.
"""

from __future__ import annotations

PLACE_FEATURE_CODES = frozenset({
    "PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLG", "PPLS",
})


def parse_open_meteo_place(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    if item.get("feature_code") not in PLACE_FEATURE_CODES:
        return None
    name = str(item.get("name") or "").strip()
    if not name:
        return None
    try:
        lat = float(item["latitude"])
        lon = float(item["longitude"])
    except (KeyError, TypeError, ValueError):
        lat = lon = None
    return {
        "name": name,
        "countryCode": str(item.get("country_code") or "").upper(),
        "country": str(item.get("country") or ""),
        "region": str(item.get("admin1") or ""),
        "population": int(item.get("population") or 0),
        "lat": lat,
        "lon": lon,
    }


def parse_nominatim_place(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    name = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("hamlet")
        or item.get("name")
        or ""
    )
    name = str(name).strip()
    if not name:
        display = str(item.get("display_name") or "")
        name = display.split(",", 1)[0].strip()
    if not name:
        return None
    kind = str(item.get("type") or item.get("addresstype") or item.get("class") or "")
    if kind and kind not in {
        "city", "town", "village", "municipality", "hamlet", "suburb",
        "administrative", "neighbourhood", "county",
    }:
        if item.get("class") not in {"place", "boundary"}:
            return None
    try:
        lat = float(item["lat"])
        lon = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    region = (
        address.get("state")
        or address.get("region")
        or address.get("county")
        or ""
    )
    return {
        "name": name,
        "countryCode": str(address.get("country_code") or "").upper(),
        "country": str(address.get("country") or ""),
        "region": str(region),
        "population": int(item.get("importance", 0) * 1_000_000),
        "lat": lat,
        "lon": lon,
    }


def place_key(place: dict) -> tuple[str, str]:
    return (str(place.get("name") or "").casefold(), str(place.get("countryCode") or "").upper())

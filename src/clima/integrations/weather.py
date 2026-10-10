"""Weather facade: OpenWeather first (when a key is set), Open-Meteo as fallback.

Подсказки мест: Open-Meteo geocoding + Nominatim (OSM) без ключа.
Города не хардкодируются — клиент держит локальный датасет, сервер ищет в API.
"""

from datetime import date
import json
import logging
from time import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from clima.cache import Cache, MemoryCache
from clima.errors import ServiceUnavailableError, ValidationError
from clima.integrations.openweather import OpenWeatherClient, OpenWeatherMiss
from clima.integrations.places import parse_nominatim_place, parse_open_meteo_place, place_key
from clima.models.value_objects import WeatherData

logger = logging.getLogger(__name__)

LOCATION_TTL_SECONDS = 30 * 24 * 3600
PLACE_SUGGEST_TTL_SECONDS = 6 * 3600
IP_CONTEXT_TTL_SECONDS = 24 * 3600
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = (
    "temperature_2m_min,temperature_2m_max,apparent_temperature_min,apparent_temperature_max,"
    "weather_code,precipitation_sum,wind_speed_10m_max,uv_index_max"
)


class WeatherService:
    apiUrl = "https://api.open-meteo.com/v1/forecast"
    geocodingUrl = "https://geocoding-api.open-meteo.com/v1/search"
    _conditions = {
        0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность",
        3: "пасмурно", 45: "туман", 48: "изморозь", 51: "морось",
        53: "морось", 55: "сильная морось", 61: "небольшой дождь",
        63: "дождь", 65: "сильный дождь", 71: "небольшой снег",
        73: "снег", 75: "сильный снег", 80: "ливень", 81: "ливень",
        82: "сильный ливень", 95: "гроза", 96: "гроза с градом",
        99: "сильная гроза с градом",
    }

    def __init__(
        self, timeout: float = 2.0, cacheSeconds: float = 600.0,
        openWeather: OpenWeatherClient | None = None, cache: Cache | None = None,
    ):
        self.timeout = timeout
        self.openWeather = openWeather
        self.cacheSeconds = cacheSeconds
        self.cache: Cache = cache if cache is not None else MemoryCache()

    def getWeather(self, location: str) -> WeatherData:
        return self.getForecast(location, date.today())

    def getForecast(
        self, place: str, date: date,
        latitude: float | None = None, longitude: float | None = None,
    ) -> WeatherData:
        if not place.strip() and latitude is None:
            raise ValidationError("Укажите место для прогноза погоды")
        cached = self._recall(place, date, latitude, longitude)
        if cached and cached[0] > time():
            return cached[1]
        try:
            result = self._fetchForecast(place, date, latitude, longitude)
            self._remember(place, date, result, latitude=latitude, longitude=longitude)
            return result
        except ValidationError:
            raise
        except (
            ServiceUnavailableError, URLError, TimeoutError, OSError, AttributeError,
            KeyError, IndexError, TypeError, ValueError,
        ) as error:
            stale = self._recall(place, date, latitude, longitude)
            if stale:
                logger.warning(
                    "Using cached weather for %s on %s after provider failure", place, date,
                )
                return stale[1]
            if isinstance(error, ServiceUnavailableError):
                raise
            raise ServiceUnavailableError("Сервис прогноза погоды временно недоступен") from error

    def _fetchForecast(
        self, place: str, date: date,
        latitude: float | None, longitude: float | None,
    ) -> WeatherData:
        if self.openWeather is not None:
            try:
                return self.openWeather.getForecast(
                    place, date, latitude=latitude, longitude=longitude,
                )
            except OpenWeatherMiss:
                logger.info("OpenWeather has no data for %s on %s, using Open-Meteo", place, date)
            except ServiceUnavailableError as error:
                logger.warning("OpenWeather unavailable (%s), using Open-Meteo", error)
        return self._fetchFromOpenMeteo(place, date, latitude, longitude)

    def _fetchFromOpenMeteo(
        self, place: str, day: date,
        latitude: float | None, longitude: float | None,
    ) -> WeatherData:
        location = self._resolveLocation(place, latitude, longitude)
        today = date.today()
        delta = (day - today).days
        source = "forecast"
        if -92 <= delta <= 16:
            payload = self._get_json(self.apiUrl, {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "daily": DAILY_VARS,
                "timezone": "auto",
                "forecast_days": min(16, max(1, delta + 1)),
                "past_days": min(92, max(0, -delta)),
            })
        elif delta < -92:
            payload = self._get_json(ARCHIVE_URL, {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "start_date": day.isoformat(),
                "end_date": day.isoformat(),
                "daily": DAILY_VARS,
                "timezone": "auto",
            })
            source = "archive"
        else:
            seasonal = day.replace(year=today.year - 1) if day.month != 2 or day.day != 29 else date(today.year - 1, 2, 28)
            payload = self._get_json(ARCHIVE_URL, {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "start_date": seasonal.isoformat(),
                "end_date": seasonal.isoformat(),
                "daily": DAILY_VARS,
                "timezone": "auto",
            })
            source = "seasonal"
        return self._dailyToWeather(payload, location, place, day, source)

    def _dailyToWeather(
        self, forecast: dict, location: dict, place: str, day: date, source: str,
    ) -> WeatherData:
        days = forecast.get("daily", {}).get("time", [])
        target = day.isoformat()
        if source == "seasonal" and days:
            index = 0
        else:
            try:
                index = days.index(target)
            except ValueError as error:
                if days:
                    index = 0
                else:
                    raise ValidationError("Прогноз для этой даты недоступен") from error
        daily = forecast["daily"]

        def _num(key: str, default: float = 0.0) -> float:
            values = daily.get(key) or []
            if index >= len(values) or values[index] is None:
                return default
            try:
                return float(values[index])
            except (TypeError, ValueError):
                return default

        tmin, tmax = _num("temperature_2m_min"), _num("temperature_2m_max")
        amin, amax = _num("apparent_temperature_min", tmin), _num("apparent_temperature_max", tmax)
        temperature = round((tmin + tmax) / 2)
        feels = round((amin + amax) / 2)
        weather_code = int(_num("weather_code"))
        return WeatherData(
            place=location.get("name", place), date=day, temperature=temperature,
            conditions=self._conditions.get(weather_code, "неизвестные условия"),
            feelsLike=feels,
            windSpeed=_num("wind_speed_10m_max"),
            humidity=0,
            precipitation=_num("precipitation_sum"),
            uvIndex=_num("uv_index_max"),
            latitude=float(location["latitude"]),
            longitude=float(location["longitude"]),
            source=source,
        )

    def suggestPlaces(
        self, query: str, country_code: str | None = None, seed: str | None = None,
        client_ip: str = "", limit: int = 10,
    ) -> list[dict]:
        limit = max(1, min(limit, 100))
        trimmed = (query or "").strip()
        if len(trimmed) >= 2:
            return self._searchPlaces(trimmed, country_code, limit)
        return self._defaultPlaces(country_code, seed, client_ip, limit)

    def placeContext(self, client_ip: str = "") -> dict:
        context = self._ipContext(client_ip)
        country = (context.get("countryCode") or "").upper()
        return {
            "countryCode": country,
            "city": context.get("city") or "",
            "region": context.get("regionName") or "",
        }

    def _defaultPlaces(
        self, country_code: str | None, seed: str | None, client_ip: str, limit: int,
    ) -> list[dict]:
        country = (country_code or "").upper()
        context = self._ipContext(client_ip)
        if not country and context.get("countryCode"):
            country = context["countryCode"].upper()
        seeds: list[str] = []
        if seed and seed.strip():
            seeds.append(seed.strip())
        if country and context.get("countryCode", "").upper() == country:
            for value in (context.get("city"), context.get("regionName")):
                if value and value not in seeds:
                    seeds.append(value)
        merged: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for name in seeds:
            for place in self._searchPlaces(name, country or None, min(40, limit * 2)):
                key = place_key(place)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(place)
        if country and len(merged) < limit:
            for place in self._nominatimSearch("", country, limit):
                key = place_key(place)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(place)
        merged.sort(key=lambda item: (-item.get("population", 0), item["name"]))
        return merged[:limit]

    def _searchPlaces(self, query: str, country_code: str | None, limit: int) -> list[dict]:
        key = f"places:suggest:{country_code or ''}:{query.casefold()}:{limit}"
        cached = self.cache.get(key)
        if cached:
            try:
                return json.loads(cached)
            except ValueError:
                pass
        params: dict = {"name": query, "count": min(max(limit * 2, 20), 100), "language": "ru"}
        if country_code:
            params["countryCode"] = country_code.upper()
        geo = self._get_json(self.geocodingUrl, params)
        places = [
            parsed for parsed in (
                parse_open_meteo_place(item) for item in (geo.get("results") or [])
            ) if parsed
        ]
        if len(places) < limit:
            seen = {place_key(place) for place in places}
            for place in self._nominatimSearch(query, country_code, limit):
                key_place = place_key(place)
                if key_place in seen:
                    continue
                seen.add(key_place)
                places.append(place)
        places.sort(key=lambda item: (-item.get("population", 0), item["name"]))
        places = places[:limit]
        self.cache.set(key, json.dumps(places, ensure_ascii=False), PLACE_SUGGEST_TTL_SECONDS)
        return places

    def _nominatimSearch(self, query: str, country_code: str | None, limit: int) -> list[dict]:
        params = {
            "format": "json",
            "addressdetails": 1,
            "limit": min(limit, 50),
            "featuretype": "city",
        }
        if country_code:
            params["countrycodes"] = country_code.lower()
        params["q"] = query.strip() if query.strip() else (country_code or "city")
        try:
            payload = self._get_json(NOMINATIM_URL, params)
        except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            return []
        if not isinstance(payload, list):
            return []
        places = [parsed for parsed in (parse_nominatim_place(item) for item in payload) if parsed]
        return places

    def _resolveLocation(
        self, place: str, latitude: float | None, longitude: float | None,
    ) -> dict:
        if latitude is not None and longitude is not None:
            return {
                "name": place.strip() or "место",
                "latitude": float(latitude),
                "longitude": float(longitude),
            }
        return self._getLocation(place)

    def _getLocation(self, place: str) -> dict:
        key = f"weather:om-geo:{place.strip().casefold()}"
        cached = self.cache.get(key)
        if cached:
            try:
                return json.loads(cached)
            except ValueError:
                pass
        geo = self._get_json(
            self.geocodingUrl, {"name": place, "count": 1, "language": "ru"}
        )
        locations = geo.get("results") or []
        if not locations:
            extras = self._nominatimSearch(place, None, 1)
            if extras:
                location = {
                    "name": extras[0]["name"],
                    "latitude": extras[0]["lat"],
                    "longitude": extras[0]["lon"],
                }
                self.cache.set(key, json.dumps(location, ensure_ascii=False), LOCATION_TTL_SECONDS)
                return location
            raise ValidationError(f"Не удалось найти место: {place}")
        location = locations[0]
        self.cache.set(key, json.dumps(location, ensure_ascii=False), LOCATION_TTL_SECONDS)
        return location

    def _ipContext(self, client_ip: str) -> dict:
        ip = (client_ip or "").strip()
        if not ip or ip.startswith(("127.", "10.", "192.168.", "::1", "fe80:")):
            return {}
        cache_key = f"places:ip:{ip}"
        cached = self.cache.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except ValueError:
                pass
        try:
            payload = self._get_json(
                f"http://ip-api.com/json/{ip}",
                {"fields": "status,countryCode,city,regionName"},
            )
        except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            return {}
        if payload.get("status") != "success":
            return {}
        context = {
            "countryCode": (payload.get("countryCode") or "").upper(),
            "city": payload.get("city") or "",
            "regionName": payload.get("regionName") or "",
        }
        self.cache.set(cache_key, json.dumps(context, ensure_ascii=False), IP_CONTEXT_TTL_SECONDS)
        return context

    @staticmethod
    def _forecastKey(
        place: str, day: date, latitude: float | None = None, longitude: float | None = None,
    ) -> str:
        if latitude is not None and longitude is not None:
            return f"weather:forecast:{round(latitude, 3)}:{round(longitude, 3)}:{day.isoformat()}"
        return f"weather:forecast:{place.strip().casefold()}:{day.isoformat()}"

    def _remember(
        self, place: str, day: date, data: WeatherData, freshUntil: float | None = None,
        latitude: float | None = None, longitude: float | None = None,
    ) -> None:
        payload = json.dumps({
            "freshUntil": time() + self.cacheSeconds if freshUntil is None else freshUntil,
            "place": data.place, "date": data.date.isoformat(),
            "temperature": data.temperature, "conditions": data.conditions,
            "feelsLike": data.feelsLike, "windSpeed": data.windSpeed,
            "humidity": data.humidity, "precipitation": data.precipitation,
            "uvIndex": data.uvIndex, "latitude": data.latitude,
            "longitude": data.longitude, "source": data.source,
        }, ensure_ascii=False)
        self.cache.set(
            self._forecastKey(place, day, latitude, longitude),
            payload, 2 * self.cacheSeconds,
        )

    def _recall(
        self, place: str, day: date,
        latitude: float | None = None, longitude: float | None = None,
    ) -> tuple[float, WeatherData] | None:
        raw = self.cache.get(self._forecastKey(place, day, latitude, longitude))
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return float(payload["freshUntil"]), WeatherData(
                place=payload["place"], date=date.fromisoformat(payload["date"]),
                temperature=int(payload["temperature"]), conditions=payload["conditions"],
                feelsLike=payload.get("feelsLike"),
                windSpeed=float(payload.get("windSpeed") or 0),
                humidity=int(payload.get("humidity") or 0),
                precipitation=float(payload.get("precipitation") or 0),
                uvIndex=float(payload.get("uvIndex") or 0),
                latitude=payload.get("latitude"),
                longitude=payload.get("longitude"),
                source=payload.get("source") or "forecast",
            )
        except (ValueError, KeyError, TypeError):
            return None

    def _get_json(self, url: str, params: dict) -> dict | list:
        request = Request(
            f"{url}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": "Clima/1.0 (outfit weather app)"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

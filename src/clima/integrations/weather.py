"""Weather facade: OpenWeather first (when a key is set), Open-Meteo as fallback."""

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
from clima.models.value_objects import WeatherData

logger = logging.getLogger(__name__)

LOCATION_TTL_SECONDS = 30 * 24 * 3600


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

    def getForecast(self, place: str, date: date) -> WeatherData:
        if not place.strip():
            raise ValidationError("Укажите место для прогноза погоды")
        cached = self._recall(place, date)
        if cached and cached[0] > time():
            return cached[1]
        try:
            result = self._fetchForecast(place, date)
            self._remember(place, date, result)
            return result
        except ValidationError:
            raise
        except (
            ServiceUnavailableError, URLError, TimeoutError, OSError, AttributeError,
            KeyError, IndexError, TypeError, ValueError,
        ) as error:
            # Запись живёт в кеше 2 × cacheSeconds: вторая половина срока — «устаревший, но лучше чем ничего».
            stale = self._recall(place, date)
            if stale:
                logger.warning(
                    "Using cached weather for %s on %s after provider failure", place, date,
                )
                return stale[1]
            if isinstance(error, ServiceUnavailableError):
                raise
            raise ServiceUnavailableError("Сервис прогноза погоды временно недоступен") from error

    def _fetchForecast(self, place: str, date: date) -> WeatherData:
        if self.openWeather is not None:
            try:
                return self.openWeather.getForecast(place, date)
            except OpenWeatherMiss:
                # Место или дата вне покрытия бесплатного плана (горизонт ~5 суток) — это не сбой.
                logger.info("OpenWeather has no data for %s on %s, using Open-Meteo", place, date)
            except ServiceUnavailableError as error:
                logger.warning("OpenWeather unavailable (%s), using Open-Meteo", error)
        return self._fetchFromOpenMeteo(place, date)

    def _fetchFromOpenMeteo(self, place: str, date: date) -> WeatherData:
        location = self._getLocation(place)
        forecast = self._get_json(self.apiUrl, {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "daily": "temperature_2m_min,temperature_2m_max,weather_code",
            "timezone": "auto",
            "forecast_days": 16,
        })
        days = forecast.get("daily", {}).get("time", [])
        try:
            index = days.index(date.isoformat())
        except ValueError as error:
            raise ValidationError("Прогноз доступен не более чем на 16 дней вперёд") from error
        daily = forecast["daily"]
        temperature = round(
            (daily["temperature_2m_min"][index] + daily["temperature_2m_max"][index]) / 2
        )
        weather_code = daily["weather_code"][index]
        return WeatherData(
            place=location.get("name", place), date=date, temperature=temperature,
            conditions=self._conditions.get(weather_code, "неизвестные условия"),
        )

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
            raise ValidationError(f"Не удалось найти место: {place}")
        location = locations[0]
        self.cache.set(key, json.dumps(location, ensure_ascii=False), LOCATION_TTL_SECONDS)
        return location

    @staticmethod
    def _forecastKey(place: str, day: date) -> str:
        return f"weather:forecast:{place.strip().casefold()}:{day.isoformat()}"

    def _remember(
        self, place: str, day: date, data: WeatherData, freshUntil: float | None = None,
    ) -> None:
        payload = json.dumps({
            "freshUntil": time() + self.cacheSeconds if freshUntil is None else freshUntil,
            "place": data.place, "date": data.date.isoformat(),
            "temperature": data.temperature, "conditions": data.conditions,
        }, ensure_ascii=False)
        self.cache.set(self._forecastKey(place, day), payload, 2 * self.cacheSeconds)

    def _recall(self, place: str, day: date) -> tuple[float, WeatherData] | None:
        raw = self.cache.get(self._forecastKey(place, day))
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return float(payload["freshUntil"]), WeatherData(
                place=payload["place"], date=date.fromisoformat(payload["date"]),
                temperature=int(payload["temperature"]), conditions=payload["conditions"],
            )
        except (ValueError, KeyError, TypeError):
            return None

    def _get_json(self, url: str, params: dict) -> dict:
        request = Request(
            f"{url}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": "Clima/1.0"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

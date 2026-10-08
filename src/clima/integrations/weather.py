"""Weather facade: OpenWeather first (when a key is set), Open-Meteo as fallback."""

from datetime import date
import json
import logging
from threading import RLock
from time import monotonic
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from clima.errors import ServiceUnavailableError, ValidationError
from clima.integrations.openweather import OpenWeatherClient, OpenWeatherMiss
from clima.models.value_objects import WeatherData

logger = logging.getLogger(__name__)


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
        openWeather: OpenWeatherClient | None = None,
    ):
        self.timeout = timeout
        self.openWeather = openWeather
        self.cacheSeconds = cacheSeconds
        self._lock = RLock()
        self._locations: dict[str, tuple[float, dict]] = {}
        self._forecasts: dict[tuple[str, date], tuple[float, WeatherData]] = {}

    def getWeather(self, location: str) -> WeatherData:
        return self.getForecast(location, date.today())

    def getForecast(self, place: str, date: date) -> WeatherData:
        if not place.strip():
            raise ValidationError("Укажите место для прогноза погоды")
        cache_key = (place.strip().casefold(), date)
        with self._lock:
            cached = self._forecasts.get(cache_key)
            if cached and cached[0] > monotonic():
                return cached[1]
        try:
            result = self._fetchForecast(place, date)
            with self._lock:
                self._forecasts[cache_key] = (monotonic() + self.cacheSeconds, result)
            return result
        except ValidationError:
            raise
        except (
            ServiceUnavailableError, URLError, TimeoutError, OSError, AttributeError,
            KeyError, IndexError, TypeError, ValueError,
        ) as error:
            now = monotonic()
            with self._lock:
                cached = self._forecasts.get(cache_key)
                if cached and cached[0] + self.cacheSeconds > now:
                    logger.warning(
                        "Using cached weather for %s on %s after provider failure",
                        place,
                        date,
                    )
                    return cached[1]
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
        key = place.strip().casefold()
        with self._lock:
            cached = self._locations.get(key)
            if cached and cached[0] > monotonic():
                return cached[1]
        geo = self._get_json(
            self.geocodingUrl, {"name": place, "count": 1, "language": "ru"}
        )
        locations = geo.get("results") or []
        if not locations:
            raise ValidationError(f"Не удалось найти место: {place}")
        location = locations[0]
        with self._lock:
            self._locations[key] = (monotonic() + 30 * 24 * 3600, location)
        return location

    def _get_json(self, url: str, params: dict) -> dict:
        request = Request(
            f"{url}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": "Clima/1.0"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

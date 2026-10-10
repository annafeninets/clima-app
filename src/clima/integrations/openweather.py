"""OpenWeather integration (free plan: geocoding + 5 day / 3 hour forecast).

Бесплатный ключ OpenWeather отдаёт прогноз только на ~5 суток вперёд с шагом
3 часа, поэтому клиент агрегирует слоты в один «день» и сообщает о выходе за
горизонт через ``OpenWeatherMiss`` — вызывающий код (WeatherService) тогда
переключается на запасного провайдера.
"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from clima.cache import Cache, MemoryCache
from clima.errors import ServiceUnavailableError
from clima.models.value_objects import WeatherData

logger = logging.getLogger(__name__)


class OpenWeatherMiss(Exception):
    """OpenWeather отработал, но данных для запроса у него нет (место/дата вне покрытия)."""


# Те же формулировки, что и у Open-Meteo, — controllers/outfits.py ищет в них
# подстроки «дожд», «лив», «снег», «гроз», «ясно».
_CONDITIONS = {
    200: "гроза", 201: "гроза", 202: "гроза", 210: "гроза", 211: "гроза",
    212: "гроза", 221: "гроза", 230: "гроза", 231: "гроза", 232: "гроза",
    300: "морось", 301: "морось", 302: "сильная морось", 310: "морось",
    311: "морось", 312: "сильная морось", 313: "ливень", 314: "ливень",
    321: "ливень",
    500: "небольшой дождь", 501: "дождь", 502: "сильный дождь",
    503: "сильный дождь", 504: "сильный дождь", 511: "ледяной дождь",
    520: "ливень", 521: "ливень", 522: "сильный ливень", 531: "ливень",
    600: "небольшой снег", 601: "снег", 602: "сильный снег",
    611: "дождь со снегом", 612: "дождь со снегом", 613: "дождь со снегом",
    615: "дождь со снегом", 616: "дождь со снегом",
    620: "небольшой снег", 621: "снег", 622: "сильный снег",
    701: "туман", 721: "туман", 741: "туман",
    800: "ясно", 801: "преимущественно ясно", 802: "переменная облачность",
    803: "облачно", 804: "пасмурно",
}


def _severity(weatherId: int) -> int:
    """Чем выше число, тем «хуже» погода: как и weather_code в Open-Meteo, берём самое неприятное за день."""
    if 200 <= weatherId < 300:
        return 5
    if 600 <= weatherId < 700:
        return 4
    if 300 <= weatherId < 600:
        return 3
    if 700 <= weatherId < 800:
        return 2
    if 801 <= weatherId < 900:
        return 1
    return 0


class OpenWeatherClient:
    geocodingUrl = "https://api.openweathermap.org/geo/1.0/direct"
    forecastUrl = "https://api.openweathermap.org/data/2.5/forecast"

    def __init__(self, apiKey: str, timeout: float = 2.0, cache: Cache | None = None):
        apiKey = apiKey.strip()
        if not apiKey:
            raise ValueError("OpenWeather API key is empty")
        self._apiKey = apiKey
        self.timeout = timeout
        self.cache: Cache = cache if cache is not None else MemoryCache()
        self._authWarned = False

    def getForecast(
        self, place: str, day: date,
        latitude: float | None = None, longitude: float | None = None,
    ) -> WeatherData:
        if latitude is not None and longitude is not None:
            location = {"name": place.strip() or "место", "lat": float(latitude), "lon": float(longitude)}
        else:
            location = self._getLocation(place)
        forecast = self._get_json(self.forecastUrl, {
            "lat": location["lat"], "lon": location["lon"],
            "units": "metric", "lang": "ru",
        })
        try:
            offset = timedelta(seconds=int(forecast["city"].get("timezone", 0)))
            slots = []
            for entry in forecast["list"]:
                local = datetime.fromtimestamp(entry["dt"], tz=timezone.utc) + offset
                if local.date() == day:
                    slots.append(entry)
            if not slots:
                raise OpenWeatherMiss(f"No OpenWeather slots for {day.isoformat()}")
            temps = [float(slot["main"]["temp"]) for slot in slots]
            temperature = round((min(temps) + max(temps)) / 2)
            conditions = self._pickConditions(slots)
            feels = [
                float(slot["main"]["feels_like"])
                for slot in slots if slot.get("main", {}).get("feels_like") is not None
            ]
            winds = [
                float(slot.get("wind", {}).get("speed") or 0) * 3.6 for slot in slots
            ]
            humidity = [
                int(slot["main"]["humidity"])
                for slot in slots if slot.get("main", {}).get("humidity") is not None
            ]
            rain = 0.0
            for slot in slots:
                rain += float((slot.get("rain") or {}).get("3h") or 0)
                rain += float((slot.get("snow") or {}).get("3h") or 0)
        except OpenWeatherMiss:
            raise
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
            raise ServiceUnavailableError("Ответ OpenWeather имеет неожиданный формат") from error
        return WeatherData(
            place=location["name"], date=day, temperature=temperature, conditions=conditions,
            feelsLike=round(sum(feels) / len(feels)) if feels else temperature,
            windSpeed=max(winds) if winds else 0.0,
            humidity=round(sum(humidity) / len(humidity)) if humidity else 0,
            precipitation=rain,
            uvIndex=0.0,
            latitude=location["lat"],
            longitude=location["lon"],
            source="forecast",
        )

    @staticmethod
    def _pickConditions(slots: list[dict]) -> str:
        ids: list[int] = []
        descriptions: dict[int, str] = {}
        for slot in slots:
            weather = slot["weather"][0]
            weatherId = int(weather["id"])
            ids.append(weatherId)
            descriptions.setdefault(weatherId, str(weather.get("description", "")).strip())
        worst = max(_severity(weatherId) for weatherId in ids)
        candidates = Counter(w for w in ids if _severity(w) == worst)
        weatherId = candidates.most_common(1)[0][0]
        return _CONDITIONS.get(weatherId) or descriptions.get(weatherId) or "неизвестные условия"

    def _getLocation(self, place: str) -> dict:
        key = f"weather:ow-geo:{place.strip().casefold()}"
        cached = self.cache.get(key)
        if cached:
            try:
                return json.loads(cached)
            except ValueError:
                pass
        found = self._get_json(self.geocodingUrl, {"q": place.strip(), "limit": 1})
        if not isinstance(found, list) or not found:
            raise OpenWeatherMiss(f"OpenWeather не нашёл место: {place}")
        first = found[0]
        try:
            location = {
                "name": (first.get("local_names") or {}).get("ru") or first["name"],
                "lat": float(first["lat"]), "lon": float(first["lon"]),
            }
        except (KeyError, TypeError, ValueError) as error:
            raise ServiceUnavailableError("Ответ геокодера OpenWeather имеет неожиданный формат") from error
        self.cache.set(key, json.dumps(location, ensure_ascii=False), 30 * 24 * 3600)
        return location

    def _get_json(self, url: str, params: dict):
        # appid добавляем только здесь и нигде не логируем URL целиком — иначе ключ утечёт в логи.
        request = Request(
            f"{url}?{urlencode({**params, 'appid': self._apiKey})}",
            headers={"Accept": "application/json", "User-Agent": "Clima/1.0"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 401:
                # Новый ключ OpenWeather активируется не сразу (обычно до пары часов).
                if not self._authWarned:
                    logger.warning(
                        "OpenWeather отклонил API-ключ (401): ключ неверный или ещё не активирован"
                    )
                    self._authWarned = True
                raise ServiceUnavailableError("OpenWeather отклонил API-ключ") from None
            if error.code == 429:
                raise ServiceUnavailableError("Превышен лимит запросов OpenWeather") from None
            raise ServiceUnavailableError(f"OpenWeather вернул HTTP {error.code}") from None
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise ServiceUnavailableError("OpenWeather недоступен") from error

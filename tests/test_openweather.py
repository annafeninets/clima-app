from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from urllib.error import URLError

from clima.errors import ServiceUnavailableError, ValidationError
from clima.integrations.openweather import OpenWeatherClient, OpenWeatherMiss
from clima.integrations.weather import WeatherService

KEY = "test-secret-key-123"


def slot(local: datetime, offset_hours: int, temp: float, weather_id: int, description: str = ""):
    utc = local - timedelta(hours=offset_hours)
    return {
        "dt": int(utc.replace(tzinfo=timezone.utc).timestamp()),
        "main": {"temp": temp},
        "weather": [{"id": weather_id, "description": description}],
    }


def geocode(name="Moscow", ru=None):
    entry = {"name": name, "lat": 55.75, "lon": 37.61, "country": "RU"}
    if ru:
        entry["local_names"] = {"ru": ru}
    return [entry]


def responder(geo, forecast):
    def fake(url, params):
        return geo if "geo" in url else forecast
    return fake


class OpenWeatherClientTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 9)
        self.client = OpenWeatherClient(KEY)

    def _forecast(self, slots, tz=3 * 3600):
        return {"city": {"timezone": tz}, "list": slots}

    def test_temperature_is_mean_of_daily_min_and_max_and_name_is_russian(self):
        slots = [
            slot(datetime(2026, 10, 9, 3), 3, 2.0, 800),
            slot(datetime(2026, 10, 9, 15), 3, 10.0, 801),
            slot(datetime(2026, 10, 10, 0), 3, -30.0, 800),  # другой день — не учитывается
        ]
        with patch.object(self.client, "_get_json",
                          side_effect=responder(geocode(ru="Москва"), self._forecast(slots))):
            result = self.client.getForecast("Moscow", self.day)
        self.assertEqual(result.place, "Москва")
        self.assertEqual(result.temperature, 6)
        self.assertEqual(result.date, self.day)

    def test_worst_condition_of_the_day_wins(self):
        slots = [
            slot(datetime(2026, 10, 9, 6), 3, 8.0, 800),
            slot(datetime(2026, 10, 9, 12), 3, 9.0, 804),
            slot(datetime(2026, 10, 9, 18), 3, 7.0, 501),
        ]
        with patch.object(self.client, "_get_json",
                          side_effect=responder(geocode(), self._forecast(slots))):
            result = self.client.getForecast("Moscow", self.day)
        self.assertEqual(result.conditions, "дождь")

    def test_slot_is_assigned_to_local_day_using_city_timezone(self):
        # 22:00 UTC при UTC+3 — уже 01:00 следующего дня
        late = slot(datetime(2026, 10, 10, 1), 3, 4.0, 600)
        early = slot(datetime(2026, 10, 9, 13), 3, 12.0, 800)
        with patch.object(self.client, "_get_json",
                          side_effect=responder(geocode(), self._forecast([early, late]))):
            today = self.client.getForecast("Moscow", self.day)
            tomorrow = self.client.getForecast("Moscow", self.day + timedelta(days=1))
        self.assertEqual(today.temperature, 12)
        self.assertEqual(tomorrow.conditions, "небольшой снег")

    def test_date_beyond_horizon_is_a_miss_not_an_error(self):
        slots = [slot(datetime(2026, 10, 9, 12), 3, 5.0, 800)]
        with patch.object(self.client, "_get_json",
                          side_effect=responder(geocode(), self._forecast(slots))):
            with self.assertRaises(OpenWeatherMiss):
                self.client.getForecast("Moscow", self.day + timedelta(days=10))

    def test_unknown_place_is_a_miss(self):
        with patch.object(self.client, "_get_json", return_value=[]):
            with self.assertRaises(OpenWeatherMiss):
                self.client.getForecast("Нигденет", self.day)

    def test_malformed_forecast_is_reported_as_unavailable(self):
        broken = {"dt": int(datetime(2026, 10, 9, 12, tzinfo=timezone.utc).timestamp())}  # нет main/weather
        with patch.object(self.client, "_get_json",
                          side_effect=responder(geocode(), {"city": {}, "list": [broken]})):
            with self.assertRaises(ServiceUnavailableError):
                self.client.getForecast("Moscow", self.day)

    def test_empty_key_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenWeatherClient("   ")

    def test_http_errors_never_expose_the_api_key(self):
        from urllib.error import HTTPError
        error = HTTPError(f"https://x/?appid={KEY}", 401, "Unauthorized", {}, None)
        with patch("clima.integrations.openweather.urlopen", side_effect=error):
            with self.assertRaises(ServiceUnavailableError) as raised:
                self.client._get_json("https://api.openweathermap.org/geo/1.0/direct", {"q": "x"})
        self.assertNotIn(KEY, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    def test_network_failure_is_reported_as_unavailable(self):
        with patch("clima.integrations.openweather.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(ServiceUnavailableError):
                self.client._get_json("https://api.openweathermap.org/geo/1.0/direct", {"q": "x"})


class WeatherServiceProviderTests(unittest.TestCase):
    def setUp(self):
        self.day = date.today()
        self.client = OpenWeatherClient(KEY)
        self.service = WeatherService(openWeather=self.client)

    def test_openweather_is_primary_and_open_meteo_is_not_called(self):
        with patch.object(self.client, "getForecast",
                          return_value=__import__("clima.models.value_objects", fromlist=["x"]).WeatherData(
                              "Москва", self.day, 7, "дождь")), \
             patch.object(self.service, "_getLocation",
                          side_effect=AssertionError("Open-Meteo не должен вызываться")):
            result = self.service.getForecast("Москва", self.day)
        self.assertEqual((result.temperature, result.conditions), (7, "дождь"))

    def test_falls_back_to_open_meteo_when_openweather_fails(self):
        meteo = {"daily": {"time": [self.day.isoformat()], "temperature_2m_min": [10],
                           "temperature_2m_max": [20], "weather_code": [61]}}
        with patch.object(self.client, "getForecast", side_effect=ServiceUnavailableError("down")), \
             patch.object(self.service, "_getLocation",
                          return_value={"name": "Москва", "latitude": 1, "longitude": 2}), \
             patch.object(self.service, "_get_json", return_value=meteo):
            result = self.service.getForecast("Москва", self.day)
        self.assertEqual((result.temperature, result.conditions), (15, "небольшой дождь"))

    def test_falls_back_to_open_meteo_beyond_openweather_horizon(self):
        far = self.day + timedelta(days=9)
        meteo = {"daily": {"time": [far.isoformat()], "temperature_2m_min": [0],
                           "temperature_2m_max": [4], "weather_code": [3]}}
        with patch.object(self.client, "getForecast", side_effect=OpenWeatherMiss("далеко")), \
             patch.object(self.service, "_getLocation",
                          return_value={"name": "Москва", "latitude": 1, "longitude": 2}), \
             patch.object(self.service, "_get_json", return_value=meteo):
            result = self.service.getForecast("Москва", far)
        self.assertEqual((result.temperature, result.conditions), (2, "пасмурно"))

    def test_unknown_place_still_reports_validation_error(self):
        with patch.object(self.client, "getForecast", side_effect=OpenWeatherMiss("нет")), \
             patch.object(self.service, "_getLocation",
                          side_effect=ValidationError("Не удалось найти место: Нигденет")):
            with self.assertRaises(ValidationError):
                self.service.getForecast("Нигденет", self.day)

    def test_both_providers_down_reports_service_unavailable(self):
        with patch.object(self.client, "getForecast", side_effect=ServiceUnavailableError("down")), \
             patch.object(self.service, "_getLocation", side_effect=URLError("offline")):
            with self.assertRaises(ServiceUnavailableError):
                self.service.getForecast("Москва", self.day)


if __name__ == "__main__":
    unittest.main()

"""Кеш прогноза погоды и геокодинга поверх общего Cache (без БД и сети)."""

from datetime import date
import json
from time import time
import unittest
from unittest.mock import patch
from urllib.error import URLError

from clima.cache import MemoryCache
from clima.errors import ServiceUnavailableError
from clima.integrations.weather import WeatherService
from clima.models.value_objects import WeatherData


class WeatherCacheTests(unittest.TestCase):
    def test_uses_recent_cached_forecast_when_service_is_unavailable(self):
        service = WeatherService(cacheSeconds=60)
        selected_date = date.today()
        cached = WeatherData("Moscow", selected_date, 18, "ясно")
        service._remember("Moscow", selected_date, cached, freshUntil=time() - 1)

        with patch.object(service, "_getLocation", side_effect=URLError("offline")):
            result = service.getForecast("Moscow", selected_date)

        self.assertEqual(result, cached)

    def test_without_cached_forecast_reports_service_unavailable(self):
        service = WeatherService()
        with patch.object(service, "_getLocation", side_effect=URLError("offline")):
            with self.assertRaises(ServiceUnavailableError):
                service.getForecast("Moscow", date.today())

    def test_fresh_forecast_is_served_without_calling_provider(self):
        service = WeatherService(cacheSeconds=60)
        today = date.today()
        cached = WeatherData("Moscow", today, 5, "дождь")
        service._remember("  MOSCOW ", today, cached)

        with patch.object(service, "_fetchForecast", side_effect=AssertionError("no call")):
            self.assertEqual(service.getForecast("moscow", today), cached)

    def test_successful_fetch_is_stored_in_shared_cache(self):
        cache = MemoryCache()
        first = WeatherService(cache=cache)
        today = date.today()
        fetched = WeatherData("Moscow", today, 9, "снег")
        with patch.object(first, "_fetchForecast", return_value=fetched) as fetch:
            self.assertEqual(first.getForecast("Moscow", today), fetched)
            fetch.assert_called_once()

        # другой экземпляр сервиса (например, после перезапуска) читает тот же кеш
        second = WeatherService(cache=cache)
        with patch.object(second, "_fetchForecast", side_effect=AssertionError("no call")):
            self.assertEqual(second.getForecast("Moscow", today), fetched)

    def test_corrupted_cache_entry_is_ignored(self):
        cache = MemoryCache()
        service = WeatherService(cache=cache)
        today = date.today()
        cache.set(service._forecastKey("Moscow", today), "{not json", 60)
        fetched = WeatherData("Moscow", today, 1, "ясно")
        with patch.object(service, "_fetchForecast", return_value=fetched):
            self.assertEqual(service.getForecast("Moscow", today), fetched)

    def test_geocoding_is_cached(self):
        service = WeatherService()
        geo = {"results": [{"name": "Москва", "latitude": 55.75, "longitude": 37.61}]}
        with patch.object(service, "_get_json", return_value=geo) as get_json:
            first = service._getLocation("Moscow")
            second = service._getLocation(" moscow")
        self.assertEqual(first, second)
        self.assertEqual(get_json.call_count, 1)
        self.assertEqual(json.loads(service.cache.get("weather:om-geo:moscow"))["name"], "Москва")

    def test_suggest_places_filters_populated_locations(self):
        service = WeatherService()
        geo = {
            "results": [
                {
                    "name": "Москва", "country_code": "RU", "country": "Россия",
                    "admin1": "Москва", "feature_code": "PPLC", "population": 10000000,
                },
                {
                    "name": "Московский", "country_code": "RU", "country": "Россия",
                    "admin1": "Московская область", "feature_code": "PPL", "population": 1000,
                },
                {
                    "name": "Europe", "country_code": "EU", "country": "Europe",
                    "admin1": "", "feature_code": "CONT", "population": 0,
                },
            ]
        }
        with patch.object(service, "_get_json", return_value=geo):
            places = service.suggestPlaces("Моск", "RU", limit=5)
        self.assertEqual(len(places), 2)
        self.assertEqual(places[0]["name"], "Москва")
        self.assertEqual(places[0]["countryCode"], "RU")

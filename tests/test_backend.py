import base64
from datetime import date
from http.server import ThreadingHTTPServer
import json
import struct
import tempfile
from threading import Thread
import unittest
from pathlib import Path
from urllib.request import urlopen
import zlib

from clima.container import Application
from clima.boundaries.http_gateway import create_handler
from clima.models.enums import Season
from clima.models.value_objects import Request, WeatherData


class FakeWeatherService:
    def getForecast(self, place, selected_date):
        return WeatherData(place, selected_date, 18, "ясно")

    def getWeather(self, location):
        return self.getForecast(location, date.today())


class BackendTests(unittest.TestCase):
    @staticmethod
    def png_bytes():
        def chunk(kind, data):
            content = kind + data
            return struct.pack(">I", len(data)) + content + struct.pack(
                ">I", zlib.crc32(content) & 0xFFFFFFFF
            )

        header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        pixels = zlib.compress(b"\x00\xff\x00\x00\xff")
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(
            b"IDAT", pixels
        ) + chunk(b"IEND", b"")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.app = Application(root / "test.sqlite3", root / "uploads", FakeWeatherService())
        result = self.request("POST", "/auth/register", {
            "login": "user@example.com", "password": "strong-password",
            "confirm": "strong-password",
        })
        self.assertEqual(result.status, 200)
        self.token = result.data.token

    def tearDown(self):
        self.app.close()
        self.directory.cleanup()

    def request(self, method, path, body=None, token=None, query=None):
        return self.app.api.dispatch(Request(
            action="", method=method, path=path, body=body or {}, token=token or "",
            query=query or {},
        ))

    def add_item(self, item_type, color, part):
        photo = base64.b64encode(self.png_bytes()).decode()
        draft = self.request("POST", "/wardrobe/items", {"photo": photo}, self.token)
        self.assertTrue(draft.success, draft.message)
        return self.request("PUT", "/wardrobe/items/draft", {
            "id": draft.data.id,
            "type": item_type,
            "color": color,
            "part": part,
            "seasons": [season.value for season in Season],
            "minTemperature": -10,
            "maxTemperature": 40,
        }, self.token)

    def test_authentication_and_protected_routes(self):
        unauthorized = self.request("GET", "/wardrobe")
        self.assertEqual(unauthorized.status, 401)
        login = self.request("POST", "/auth/login", {
            "login": "user@example.com", "password": "strong-password",
        })
        self.assertTrue(login.success)
        self.assertNotEqual(login.data.token, self.token)
        profile = self.request("GET", "/profile", token=self.token)
        self.assertTrue(profile.success)

    def test_wardrobe_outfits_rating_and_favorites(self):
        first_item = self.add_item("shirt", "white", "TOP")
        pants = self.add_item("pants", "black", "BOTTOM")
        self.assertTrue(first_item.success)
        self.assertTrue(pants.success)
        extra_top = self.add_item("sweater", "blue", "TOP")
        skirt = self.add_item("skirt", "beige", "BOTTOM")
        self.assertTrue(extra_top.success)
        self.assertTrue(skirt.success)
        other_user = self.request("POST", "/auth/register", {
            "login": "other@example.com", "password": "other-password",
            "confirm": "other-password",
        })
        forbidden = self.request(
            "GET", f"/wardrobe/items/{first_item.data.id}", token=other_user.data.token
        )
        self.assertEqual(forbidden.status, 403)
        planned = self.request(
            "GET", "/outfits/plan", token=self.token,
            query={"date": date.today().isoformat(), "place": "Moscow", "occasion": "everyday"},
        )
        self.assertTrue(planned.success, planned.message)
        self.assertEqual(len(planned.data), 3)
        outfit = planned.data[0]
        selected = self.request("POST", f"/outfits/{outfit.id}/select", token=self.token)
        self.assertTrue(selected.success)
        rated = self.request("PUT", f"/outfits/{outfit.id}/rating", {"score": 5}, self.token)
        self.assertTrue(rated.success)
        favorite = self.request(
            "POST", "/favorites", {"outfitId": outfit.id}, self.token
        )
        self.assertTrue(favorite.success)
        edited = self.request(
            "PUT", f"/favorites/{favorite.data.id}/items/{first_item.data.id}",
            {"itemId": extra_top.data.id}, self.token,
        )
        self.assertTrue(edited.success, edited.message)
        self.assertIn(extra_top.data.id, [item.id for item in edited.data.items])
        listed = self.request("GET", "/favorites", token=self.token)
        self.assertEqual(len(listed.data), 1)
        removed = self.request(
            "DELETE", f"/favorites/{favorite.data.id}", token=self.token
        )
        self.assertTrue(removed.success)

    def test_profile_theme_and_notification_settings(self):
        saved = self.request("PUT", "/profile", {
            "style": "casual", "colors": "blue,black",
            "sizes": "M", "bodyFeatures": "relaxed",
        }, self.token)
        self.assertTrue(saved.success)
        theme = self.request("PUT", "/settings/theme", {"theme": "DARK"}, self.token)
        self.assertTrue(theme.success)
        notification = self.request("PUT", "/settings/notifications", {
            "enabled": True, "time": "07:30", "timeZone": "Europe/Moscow",
        }, self.token)
        self.assertTrue(notification.success)
        settings = self.request("GET", "/settings", token=self.token)
        self.assertEqual(settings.data.theme.value, "DARK")
        self.assertEqual(settings.data.notificationTime.isoformat(timespec="minutes"), "07:30")
        self.assertEqual(settings.data.timeZone, "Europe/Moscow")

    def test_account_confirmation_and_delete(self):
        pending = self.request("DELETE", "/account", token=self.token)
        self.assertEqual(pending.status, 202)
        deleted = self.request(
            "DELETE", "/account", token=self.token, query={"confirm": "true"}
        )
        self.assertTrue(deleted.success)
        self.assertEqual(self.request("GET", "/wardrobe", token=self.token).status, 401)

    def test_http_server_dispatches_requests(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.app))
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/auth/form") as response:
                payload = json.load(response)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["data"]["fields"], ["login", "password"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

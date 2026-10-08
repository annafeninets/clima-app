import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from threading import Thread
from time import monotonic
from urllib.request import Request as HttpRequest, urlopen

from clima.api import response_bytes
from clima.boundaries.http_gateway import ClimaHTTPServer, create_handler
from clima.container import Application
from clima.errors import BadCombinationError, ValidationError
from clima.handlers.helpers import item_from_data, preferences_from_data
from clima.integrations.weather import WeatherService
from clima.models.entities import Item
from clima.models.entities.item import expected_part_for_type
from clima.models.enums import ItemPart, Season
from clima.models.value_objects import OutfitFilter, Request, WeatherData


class FakeWeatherService(WeatherService):
    def getForecast(self, place: str, date: date) -> WeatherData:
        return WeatherData(place, date, 18, "ясно")

    def getWeather(self, location: str) -> WeatherData:
        return self.getForecast(location, date.today())


from support import TEST_DATABASE_URL, drop_schema, new_schema_name, requires_database


@requires_database
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
        self.schema = new_schema_name()
        self.app = Application(
            TEST_DATABASE_URL, root / "uploads", FakeWeatherService(), databaseSchema=self.schema,
        )
        result = self.request("POST", "/auth/register", {
            "login": "user@example.com", "password": "strong-password",
            "confirm": "strong-password",
        })
        self.assertEqual(result.status, 200)
        self.token = result.data.token

    def tearDown(self):
        self.app.close()
        drop_schema(self.schema)
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
            "photo": draft.data.photo,
            "type": item_type,
            "color": color,
            "part": part,
            "seasons": [season.value for season in Season],
            "minTemperature": -10,
            "maxTemperature": 40,
            "dressCode": "casual",
            "style": "classic",
            "silhouette": "straight",
            "material": "cotton",
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
        shoes = self.add_item("sneakers", "white", "SHOES")
        self.assertTrue(first_item.success)
        self.assertTrue(pants.success)
        self.assertTrue(shoes.success)
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

    def test_dress_and_shoes_are_enough_to_generate_an_outfit(self):
        session = self.app.authController.validateSession(self.token)
        dress = Item(
            userId=session.userId,
            type="dress",
            color="black",
            seasons=list(Season),
        )
        shoes = Item(
            userId=session.userId, type="sneakers", color="white",
            part=ItemPart.SHOES, seasons=list(Season),
        )
        self.app.itemsRepository.add(dress)
        self.app.itemsRepository.add(shoes)

        outfits = self.app.outfitController.planOutfit(
            session.userId, OutfitFilter(date.today(), "Moscow", temperature=18)
        )

        self.assertEqual(len(outfits), 1)
        self.assertEqual({item.id for item in outfits[0].items}, {dress.id, shoes.id})

    def test_outfit_generation_requires_shoes(self):
        session = self.app.authController.validateSession(self.token)
        top = Item(
            userId=session.userId, type="shirt", color="white", part=ItemPart.TOP,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="straight", material="cotton",
        )
        bottom = Item(
            userId=session.userId, type="pants", color="black", part=ItemPart.BOTTOM,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="straight", material="cotton",
        )
        self.app.itemsRepository.add(top)
        self.app.itemsRepository.add(bottom)

        variants = self.app.outfitController.rule.generateVariants(
            [top, bottom], WeatherData("Moscow", date.today(), 18, "ясно")
        )
        self.assertEqual(variants, [])
        with self.assertRaises(BadCombinationError):
            self.app.outfitController.createOutfitFromItems(
                session.userId, [top.id, bottom.id]
            )

    def test_outfit_rejects_repeated_core_parts_and_accessory_types(self):
        rule = self.app.outfitController.rule

        def item(item_type, part):
            return Item(
                type=item_type, part=part, color="black", seasons=list(Season)
            )

        top = item("Футболка", ItemPart.TOP)
        second_top = item("Свитер", ItemPart.TOP)
        bottom = item("Брюки", ItemPart.BOTTOM)
        second_bottom = item("Юбка", ItemPart.BOTTOM)
        shoes = item("Кроссовки", ItemPart.SHOES)
        second_shoes = item("Ботинки", ItemPart.SHOES)
        complete = [top, bottom, shoes]

        self.assertTrue(rule.check(complete).compatible)
        self.assertIn("один верх", rule.check([*complete, second_top]).reason)
        self.assertIn("один низ", rule.check([*complete, second_bottom]).reason)
        self.assertIn("одна пара обуви", rule.check([*complete, second_shoes]).reason)

        bag = item("Сумка", ItemPart.ACCESSORY)
        backpack = item("Рюкзак", ItemPart.ACCESSORY)
        scarf = item("Шарф", ItemPart.ACCESSORY)
        snood = item("Снуд", ItemPart.ACCESSORY)
        hat = item("Шапка", ItemPart.ACCESSORY)
        cap = item("Бейсболка", ItemPart.ACCESSORY)
        self.assertTrue(rule.check([*complete, bag, scarf, hat]).compatible)
        for first, second in ((bag, backpack), (scarf, snood), (hat, cap)):
            with self.subTest(first=first.type, second=second.type):
                self.assertFalse(rule.check([*complete, first, second]).compatible)

    def test_generated_outfits_can_include_distinct_accessory_types(self):
        session = self.app.authController.validateSession(self.token)
        items = [
            Item(userId=session.userId, type="Футболка", color="белый",
                 part=ItemPart.TOP, seasons=list(Season), dressCode="casual"),
            Item(userId=session.userId, type="Брюки", color="чёрный",
                 part=ItemPart.BOTTOM, seasons=list(Season), dressCode="casual"),
            Item(userId=session.userId, type="Кроссовки", color="белый",
                 part=ItemPart.SHOES, seasons=list(Season), dressCode="casual"),
            Item(userId=session.userId, type="Сумка", color="чёрный",
                 part=ItemPart.ACCESSORY, seasons=list(Season), dressCode="casual"),
            Item(userId=session.userId, type="Шарф", color="чёрный",
                 part=ItemPart.ACCESSORY, seasons=list(Season), dressCode="casual"),
            Item(userId=session.userId, type="Шапка", color="чёрный",
                 part=ItemPart.ACCESSORY, seasons=list(Season), dressCode="casual"),
        ]
        for item in items:
            self.app.itemsRepository.add(item)

        variants = self.app.outfitController.rule.generateVariants(
            items, WeatherData("Moscow", date.today(), 5, "снег")
        )

        self.assertTrue(any(
            all(accessory in outfit.items for accessory in items[3:])
            for outfit in variants
        ))
        self.assertTrue(all(
            self.app.outfitController.rule.check(outfit.items).compatible
            for outfit in variants
        ))

    def test_item_rejects_invalid_metadata_types(self):
        with self.assertRaises(ValidationError):
            item_from_data({"type": None}, userId=1)

    def test_item_rejects_unrealistic_temperatures_and_mismatched_parts(self):
        base = Item(
            userId=1, type="джинсы", color="синий", seasons=list(Season),
            minTemperature=-10, maxTemperature=40, part=ItemPart.TOP,
            dressCode="casual", style="classic", silhouette="straight",
            material="denim",
        )
        with self.assertRaises(ValidationError):
            base.validate()
        base.part = ItemPart.BOTTOM
        base.maxTemperature = 51
        with self.assertRaises(ValidationError):
            base.validate()

    def test_item_requires_all_text_fields(self):
        valid_values = {
            "type": "рубашка", "color": "белый", "dressCode": "casual",
            "style": "classic", "silhouette": "straight", "material": "cotton",
        }
        for field in valid_values:
            for invalid_value in ("", "!!!"):
                values = {**valid_values, field: invalid_value}
                item = Item(
                    userId=1, **values, seasons=list(Season),
                    minTemperature=-10, maxTemperature=40, part=ItemPart.TOP,
                )
                with self.subTest(field=field, value=invalid_value):
                    with self.assertRaises(ValidationError):
                        item.validate()

    def test_silhouettes_are_required_and_match_item_category(self):
        base_values = {
            "color": "чёрный", "seasons": list(Season), "minTemperature": -10,
            "maxTemperature": 40, "dressCode": "casual", "style": "classic",
            "material": "leather",
        }
        for item_type, part, silhouette in (
            ("Ботинки", ItemPart.SHOES, ""),
            ("Шарф", ItemPart.ACCESSORY, "Снуд"),
            ("Сумка", ItemPart.ACCESSORY, "Кросс-боди"),
            ("Юбка", ItemPart.BOTTOM, "Трапеция"),
        ):
            with self.subTest(item_type=item_type):
                item = Item(
                    userId=1, type=item_type, part=part,
                    silhouette=silhouette, **base_values,
                )
                item.validate()
        for item_type, part, silhouette in (
            ("Шарф", ItemPart.ACCESSORY, "Кросс-боди"),
            ("Сумка", ItemPart.ACCESSORY, "Снуд"),
            ("Юбка", ItemPart.BOTTOM, "На платформе"),
        ):
            with self.subTest(item_type=item_type, silhouette=silhouette):
                invalid = Item(
                    userId=1, type=item_type, part=part,
                    silhouette=silhouette, **base_values,
                )
                with self.assertRaisesRegex(ValidationError, "Силуэт"):
                    invalid.validate()

        shoes_with_silhouette = Item(
            userId=1, type="Лоферы", part=ItemPart.SHOES,
            silhouette="Ботинки", **base_values,
        )
        with self.assertRaisesRegex(ValidationError, "Силуэт"):
            shoes_with_silhouette.validate()

        for item_type, part in (
            ("Носки", ItemPart.ACCESSORY),
            ("Перчатки", ItemPart.ACCESSORY),
            ("Ремень", ItemPart.ACCESSORY),
        ):
            with self.subTest(item_type=item_type):
                item_without_silhouette = Item(
                    userId=1, type=item_type, part=part,
                    silhouette="", **base_values,
                )
                item_without_silhouette.validate()

    def test_denim_jacket_is_validated_as_outerwear_and_keeps_legacy_part(self):
        jacket = Item(
            userId=1, type="Джинсовая куртка", color="синий",
            seasons=list(Season), minTemperature=-10, maxTemperature=20,
            part=ItemPart.OUTERWEAR, dressCode="casual", style="classic",
            silhouette="Прямой", material="Деним",
        )
        jacket.validate()
        jacket.part = ItemPart.TOP
        jacket.validate()

    def test_outerwear_names_are_classified_into_outerwear_part(self):
        for item_type in (
            "Косуха", "Пальто", "Анорак", "Пончо", "Дождевик", "Дафлкот",
            "Накидка", "raincoat",
        ):
            with self.subTest(item_type=item_type):
                self.assertEqual(
                    expected_part_for_type(item_type), ItemPart.OUTERWEAR
                )

    def test_jacket_can_layer_with_top_but_is_not_used_in_warm_weather(self):
        session = self.app.authController.validateSession(self.token)
        top = Item(
            userId=session.userId, type="t-shirt", color="white", part=ItemPart.TOP,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="straight", material="cotton",
        )
        bottom = Item(
            userId=session.userId, type="pants", color="black", part=ItemPart.BOTTOM,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="straight", material="cotton",
        )
        shoes = Item(
            userId=session.userId, type="sneakers", color="white", part=ItemPart.SHOES,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="", material="leather",
        )
        jacket = Item(
            userId=session.userId, type="jacket", color="black", part=ItemPart.OUTERWEAR,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="straight", material="denim",
        )
        scarf = Item(
            userId=session.userId, type="scarf", color="black", part=ItemPart.ACCESSORY,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="long", material="wool",
        )
        items = [top, bottom, shoes, jacket, scarf]
        for item in items:
            self.app.itemsRepository.add(item)

        warm = self.app.outfitController.rule.generateVariants(
            items, WeatherData("Moscow", date.today(), 20, "ясно")
        )
        cold = self.app.outfitController.rule.generateVariants(
            items, WeatherData("Moscow", date.today(), 5, "снег")
        )

        self.assertTrue(warm)
        self.assertTrue(all(
            item.part not in (ItemPart.OUTERWEAR, ItemPart.ACCESSORY)
            for outfit in warm for item in outfit.items
        ))
        self.assertTrue(any(
            jacket in outfit.items and scarf in outfit.items for outfit in cold
        ))

    def test_today_outfits_refresh_cached_layers_when_weather_changes(self):
        session = self.app.authController.validateSession(self.token)
        top = Item(
            userId=session.userId, type="t-shirt", color="white", part=ItemPart.TOP,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
        )
        bottom = Item(
            userId=session.userId, type="pants", color="black", part=ItemPart.BOTTOM,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
        )
        shoes = Item(
            userId=session.userId, type="sneakers", color="white", part=ItemPart.SHOES,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
        )
        jacket = Item(
            userId=session.userId, type="jacket", color="black", part=ItemPart.OUTERWEAR,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
        )
        for item in (top, bottom, shoes, jacket):
            self.app.itemsRepository.add(item)

        class MutableWeatherService(FakeWeatherService):
            temperature = 20
            conditions = "ясно"

            def getForecast(self, place: str, selected_date: date) -> WeatherData:
                return WeatherData(place, selected_date, self.temperature, self.conditions)

        weather = MutableWeatherService()
        self.app.outfitController.weatherService = weather
        warm = self.app.outfitController.getTodayOutfits(session.userId, "Moscow")
        weather.temperature = 5
        weather.conditions = "снег"
        cold = self.app.outfitController.getTodayOutfits(session.userId, "Moscow")

        self.assertTrue(warm)
        self.assertTrue(all(jacket not in outfit.items for outfit in warm))
        self.assertTrue(any(jacket in outfit.items for outfit in cold))

    def test_item_part_matches_shoes_accessories_and_one_piece_types(self):
        values = {
            "userId": 1, "color": "чёрный", "seasons": list(Season),
            "minTemperature": -10, "maxTemperature": 40, "dressCode": "casual",
            "style": "classic", "material": "leather",
        }
        for item_type, part, silhouette in (
            ("Сапоги", ItemPart.SHOES, ""),
            ("Шарф", ItemPart.ACCESSORY, "Палантин"),
        ):
            with self.subTest(item_type=item_type):
                item = Item(type=item_type, part=part, silhouette=silhouette, **values)
                item.validate()
        dress = Item(
            type="Платье", part=ItemPart.ONE_PIECE,
            silhouette="А-силуэт", **values,
        )
        dress.validate()

    def test_hat_form_values_are_accepted(self):
        hat = item_from_data({
            "type": "Шапка",
            "color": "Белый",
            "part": "ACCESSORY",
            "seasons": ["SPRING"],
            "minTemperature": 0,
            "maxTemperature": 10,
            "dressCode": "вечерний",
            "style": "Базовый",
            "material": "Атлас",
            "silhouette": "Бейсболка",
        }, userId=1)
        hat.validate()

    def test_item_without_silhouette_field_is_valid_when_not_applicable(self):
        for item_type in ("Лоферы", "Балетки"):
            with self.subTest(item_type=item_type):
                item = item_from_data({
                    "type": item_type,
                    "color": "Чёрный",
                    "part": "SHOES",
                    "seasons": ["SPRING"],
                    "minTemperature": 0,
                    "maxTemperature": 20,
                    "dressCode": "повседневный",
                    "style": "Классический",
                    "material": "Кожа",
                    "silhouette": "Прямой",
                }, userId=1)
                self.assertEqual(item.silhouette, "")
                item.validate()

    def test_generated_outfit_can_include_matching_shoes(self):
        session = self.app.authController.validateSession(self.token)
        top = Item(
            userId=session.userId, type="shirt", color="white", part=ItemPart.TOP,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="straight", material="cotton",
        )
        bottom = Item(
            userId=session.userId, type="pants", color="black", part=ItemPart.BOTTOM,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="straight", material="cotton",
        )
        shoes = Item(
            userId=session.userId, type="sneakers", color="white", part=ItemPart.SHOES,
            seasons=list(Season), minTemperature=-10, maxTemperature=40,
            dressCode="casual", style="classic", silhouette="", material="leather",
        )
        for item in (top, bottom, shoes):
            self.app.itemsRepository.add(item)
        variants = self.app.outfitController.rule.generateVariants(
            [top, bottom, shoes], WeatherData("Moscow", date.today(), 18, "ясно")
        )
        self.assertTrue(any(any(item.part == ItemPart.SHOES for item in outfit.items) for outfit in variants))

    def test_invalid_profile_and_push_payloads_return_validation_errors(self):
        profile = self.request("PUT", "/profile", {"style": ["casual"]}, self.token)
        self.assertEqual(profile.status, 422)
        invalid_preferences = self.request(
            "PUT", "/profile", {"style": "!!!", "colors": "", "sizes": "", "bodyFeatures": ""},
            self.token,
        )
        self.assertEqual(invalid_preferences.status, 422)
        invalid_location = self.request(
            "PUT", "/profile/location", {"location": "12345"}, self.token,
        )
        self.assertEqual(invalid_location.status, 422)

        subscription = self.request(
            "POST", "/push/subscriptions",
            {"endpoint": "https://push.example.test", "keys": "not-an-object"},
            self.token,
        )
        self.assertEqual(subscription.status, 422)

    def _location(self, userId):
        return self.app.database.query(
            "SELECT location FROM users WHERE id=%s", (userId,)
        )[0]["location"]

    def test_transaction_rolls_back_on_error_and_nested_one_uses_savepoint(self):
        db = self.app.database
        userId = self.app.authController.validateSession(self.token).userId

        with self.assertRaises(RuntimeError):
            with db.transaction():
                db.execute("UPDATE users SET location=%s WHERE id=%s", ("Paris", userId))
                raise RuntimeError("boom")
        self.assertEqual(self._location(userId), "")

        with db.transaction():
            db.execute("UPDATE users SET location=%s WHERE id=%s", ("Rome", userId))
            with self.assertRaises(RuntimeError):
                with db.transaction():
                    db.execute("UPDATE users SET location=%s WHERE id=%s", ("Oslo", userId))
                    raise RuntimeError("inner")
        self.assertEqual(self._location(userId), "Rome")

    def test_duplicate_registration_is_case_insensitive(self):
        again = self.request("POST", "/auth/register", {
            "login": "USER@example.com", "password": "strong-password",
            "confirm": "strong-password",
        })
        self.assertEqual(again.status, 422)

    def test_delete_account_cascades_to_all_user_data(self):
        db = self.app.database
        userId = self.app.authController.validateSession(self.token).userId
        self.add_item("Футболка", "белый", "TOP")
        self.assertEqual(
            db.query("SELECT count(*) AS n FROM items WHERE user_id=%s", (userId,))[0]["n"], 1
        )
        self.app.authController.deleteAccount(userId)
        for table in ("items", "outfits", "favorites", "sessions"):
            count = db.query(f"SELECT count(*) AS n FROM {table} WHERE user_id=%s", (userId,))
            self.assertEqual(count[0]["n"], 0, table)

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

    def test_push_subscription_and_preferences_are_saved_without_exposing_keys(self):
        saved = self.request("POST", "/push/subscribe", {
            "subscription": {
                "endpoint": "https://push.example.test/send/token",
                "keys": {"p256dh": "public-key", "auth": "auth-key"},
            },
            "time": "06:45",
            "timezone": "Europe/Moscow",
        }, self.token)
        self.assertTrue(saved.success)

        settings = self.request("GET", "/settings", token=self.token)
        self.assertTrue(settings.data.notificationsEnabled)
        self.assertEqual(settings.data.notificationTime.isoformat(timespec="minutes"), "06:45")
        self.assertEqual(settings.data.timeZone, "Europe/Moscow")
        payload, _ = response_bytes(settings)
        serialized = json.loads(payload)
        self.assertTrue(serialized["data"]["pushSubscribed"])
        self.assertNotIn("pushSubscription", serialized["data"])
        self.assertNotIn("endpoint", serialized["data"])

        removed = self.request("DELETE", "/push/subscriptions", token=self.token)
        self.assertTrue(removed.success)
        settings = self.request("GET", "/settings", token=self.token)
        self.assertFalse(settings.data.pushSubscription)

    def test_push_subscription_rejects_invalid_timezone_before_saving(self):
        response = self.request("POST", "/push/subscribe", {
            "subscription": {
                "endpoint": "https://push.example.test/send/token",
                "keys": {"p256dh": "public-key", "auth": "auth-key"},
            },
            "time": "06:45",
            "timezone": "Invalid/Zone",
        }, self.token)
        self.assertEqual(response.status, 422)
        settings = self.request("GET", "/settings", token=self.token)
        self.assertIsNone(settings.data.pushSubscription)

    def test_account_confirmation_and_delete(self):
        pending = self.request("DELETE", "/account", token=self.token)
        self.assertEqual(pending.status, 202)
        deleted = self.request(
            "DELETE", "/account", token=self.token, query={"confirm": "true"}
        )
        self.assertTrue(deleted.success)
        self.assertEqual(self.request("GET", "/wardrobe", token=self.token).status, 401)

    def test_http_server_dispatches_requests(self):
        server = ClimaHTTPServer(("127.0.0.1", 0), create_handler(self.app))
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

    def test_http_server_handles_50_concurrent_authenticated_requests(self):
        server = ClimaHTTPServer(("127.0.0.1", 0), create_handler(self.app))
        thread = Thread(target=server.serve_forever)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/settings"

        def get_settings(_):
            request = HttpRequest(url, headers={"Authorization": f"Bearer {self.token}"})
            with urlopen(request, timeout=3) as response:
                payload = json.load(response)
                self.assertEqual(response.status, 200)
                self.assertTrue(payload["success"])

        started = monotonic()
        try:
            with ThreadPoolExecutor(max_workers=50) as executor:
                list(executor.map(get_settings, range(50)))
            self.assertLess(monotonic() - started, 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

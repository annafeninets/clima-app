"""Тесты правил сочетаемости (outfit_rules): погода, повод, цвет, формальность, сезоны.

БД не нужна: запуск — ``python -m unittest tests.test_outfit_rules`` или через pytest.
"""

from datetime import date
import unittest

from clima.models.entities import Item
from clima.models.enums import ItemPart, Season
from clima.models.value_objects import WeatherData
from clima.outfit_rules import (
    BAND_RULES,
    CompatibilityRule,
    Occasion,
    TemperatureBand,
    band_for_feels_like,
    catalog_entry_for,
    normalize_occasion,
    profile_from_weather,
    season_for,
    wind_chill,
)

ALL_SEASONS = list(Season)
_ids = iter(range(1, 10_000))


def make(item_type, part, color="black", **kwargs):
    values = {
        "id": next(_ids), "userId": 1, "type": item_type, "part": part, "color": color,
        "seasons": ALL_SEASONS, "minTemperature": -30, "maxTemperature": 40,
        "dressCode": "casual", "style": "classic", "material": "",
    }
    values.update(kwargs)
    return Item(**values)


def weather(temp, feels=None, wind=0.0, rain=0.0, uv=3.0, lat=50.0, day=date(2026, 10, 10),
            conditions="ясно"):
    return WeatherData(
        place="Тест", date=day, temperature=temp, conditions=conditions,
        feelsLike=temp if feels is None else feels, windSpeed=wind, precipitation=rain,
        uvIndex=uv, latitude=lat, longitude=10.0,
    )


def wardrobe():
    return {
        "tshirt": make("Футболка", ItemPart.TOP, "белый"),
        "shirt": make("Рубашка", ItemPart.TOP, "голубой", dressCode="office"),
        "sweater": make("Свитер", ItemPart.TOP, "серый", material="wool"),
        "hoodie": make("Худи", ItemPart.TOP, "серый"),
        "jeans": make("Джинсы", ItemPart.BOTTOM, "синий", material="denim"),
        "shorts": make("Шорты", ItemPart.BOTTOM, "бежевый"),
        "pants": make("Брюки", ItemPart.BOTTOM, "чёрный", dressCode="office"),
        "sneakers": make("Кроссовки", ItemPart.SHOES, "белый"),
        "boots": make("Ботинки", ItemPart.SHOES, "коричневый"),
        "oxford": make("Туфли", ItemPart.SHOES, "чёрный", dressCode="formal"),
        "sandals": make("Сандалии", ItemPart.SHOES, "коричневый"),
        "jacket": make("Куртка", ItemPart.OUTERWEAR, "чёрный"),
        "down": make("Пуховик", ItemPart.OUTERWEAR, "чёрный"),
        "blazer": make("Блейзер", ItemPart.OUTERWEAR, "чёрный", dressCode="formal"),
        "scarf": make("Шарф", ItemPart.ACCESSORY, "серый"),
        "panama": make("Панама", ItemPart.ACCESSORY, "бежевый"),
    }


def types(outfit):
    return {item.type for item in outfit.items}


class TemperatureBandTests(unittest.TestCase):
    def test_boundaries_follow_the_spec_table(self):
        expected = {
            29: TemperatureBand.HOT, 28: TemperatureBand.WARM, 20: TemperatureBand.WARM,
            19: TemperatureBand.MILD, 12: TemperatureBand.MILD, 11: TemperatureBand.CHILLY,
            5: TemperatureBand.CHILLY, 4: TemperatureBand.COLD, -5: TemperatureBand.COLD,
            -6: TemperatureBand.FREEZING,
        }
        for feels, band in expected.items():
            with self.subTest(feels=feels):
                self.assertEqual(band_for_feels_like(feels), band)

    def test_wind_chill_lowers_feels_like_only_in_cold_wind(self):
        self.assertLess(wind_chill(0, 30), 0)
        self.assertEqual(wind_chill(15, 30), 15)
        self.assertEqual(wind_chill(0, 2), 0)

    def test_profile_uses_feels_like_not_air_temperature(self):
        profile = profile_from_weather(weather(10, feels=-7))
        self.assertEqual(profile.band, TemperatureBand.FREEZING)

    def test_rain_in_conditions_implies_precipitation(self):
        profile = profile_from_weather(weather(15, conditions="небольшой дождь"))
        self.assertGreater(profile.precipitation, 0)

    def test_every_band_has_a_rule(self):
        self.assertEqual(set(BAND_RULES), set(TemperatureBand))


class SeasonTests(unittest.TestCase):
    def test_northern_hemisphere(self):
        self.assertEqual(season_for(date(2026, 1, 15), 55.7), Season.WINTER)
        self.assertEqual(season_for(date(2026, 7, 15), 55.7), Season.SUMMER)

    def test_southern_hemisphere_is_shifted_by_half_a_year(self):
        self.assertEqual(season_for(date(2026, 7, 15), -33.9), Season.WINTER)
        self.assertEqual(season_for(date(2026, 1, 15), -33.9), Season.SUMMER)
        self.assertEqual(season_for(date(2026, 4, 15), -33.9), Season.AUTUMN)

    def test_southern_city_gets_winter_clothes_in_july(self):
        rule = CompatibilityRule()
        w = wardrobe()
        winter_only = [
            make("Свитер", ItemPart.TOP, "серый", seasons=[Season.WINTER]),
            make("Джинсы", ItemPart.BOTTOM, "синий", material="denim", seasons=[Season.WINTER]),
            make("Ботинки", ItemPart.SHOES, "коричневый", seasons=[Season.WINTER]),
            make("Куртка", ItemPart.OUTERWEAR, "чёрный", seasons=[Season.WINTER]),
        ]
        july = date(2026, 7, 15)
        self.assertTrue(rule.generateVariants(winter_only, weather(9, lat=-33.9, day=july)))
        self.assertFalse(rule.generateVariants(winter_only, weather(9, lat=50.0, day=july)))
        self.assertIn(w["jeans"], w.values())


class WeatherRuleTests(unittest.TestCase):
    def setUp(self):
        self.rule = CompatibilityRule()
        self.w = wardrobe()

    def variants(self, wthr, occasion="everyday", keys=None):
        items = list(self.w.values()) if keys is None else [self.w[key] for key in keys]
        return self.rule.generateVariants(items, wthr, occasion)

    def test_freezing_never_returns_summer_or_light_outfits(self):
        outfits = self.variants(weather(-12, feels=-18, wind=15))
        self.assertTrue(outfits)
        for outfit in outfits:
            with self.subTest(items=types(outfit)):
                self.assertTrue(types(outfit) & {"Пуховик"})
                self.assertFalse(types(outfit) & {"Шорты", "Сандалии", "Кроссовки", "Панама"})

    def test_freezing_light_wardrobe_gives_no_outfit_instead_of_a_wrong_one(self):
        self.assertEqual(
            self.variants(weather(-12, feels=-18), keys=["tshirt", "jeans", "sneakers", "jacket"]),
            [],
        )

    def test_hot_excludes_warm_clothes_and_prefers_shorts(self):
        outfits = self.variants(weather(35, feels=37, uv=9))
        self.assertTrue(outfits)
        for outfit in outfits:
            self.assertFalse(types(outfit) & {"Свитер", "Худи", "Пуховик", "Ботинки", "Шарф", "Куртка"})
        self.assertIn("Шорты", types(outfits[0]))
        self.assertIn("Панама", types(outfits[0]))

    def test_chilly_excludes_shorts_sandals_and_summer_hat(self):
        for outfit in self.variants(weather(8, feels=7, wind=20)):
            self.assertFalse(types(outfit) & {"Шорты", "Сандалии", "Панама"})
            self.assertTrue(any(item.part == ItemPart.OUTERWEAR for item in outfit.items))

    def test_rain_forbids_sandals_even_when_warm(self):
        for outfit in self.variants(weather(24, feels=24, rain=4.0, conditions="дождь")):
            self.assertNotIn("Сандалии", types(outfit))

    def test_outerwear_only_when_needed(self):
        for outfit in self.variants(weather(24, feels=24)):
            self.assertFalse(any(item.part == ItemPart.OUTERWEAR for item in outfit.items))
        self.assertTrue(any(
            item.part == ItemPart.OUTERWEAR
            for outfit in self.variants(weather(24, feels=24, rain=3.0, conditions="дождь"))
            for item in outfit.items
        ))

    def test_weather_check_explains_why_an_outfit_is_rejected(self):
        result = self.rule.weatherCheck(
            [self.w["tshirt"], self.w["shorts"], self.w["sandals"]], weather(8, feels=7)
        )
        self.assertFalse(result.compatible)
        self.assertIn("chilly", result.reason)

    def test_different_cities_give_different_outfits(self):
        moscow = self.variants(weather(-12, feels=-18, lat=55.7, day=date(2026, 1, 15)))
        cairo = self.variants(weather(34, feels=35, lat=30.0, day=date(2026, 7, 15)))
        self.assertTrue(moscow and cairo)
        self.assertFalse({tuple(sorted(types(o))) for o in moscow}
                         & {tuple(sorted(types(o))) for o in cairo})

    def test_debug_panel_data_is_filled(self):
        outfit = self.variants(weather(8, feels=7, wind=20))[0]
        debug = outfit.debug
        self.assertEqual(debug["band"], "chilly")
        self.assertEqual(debug["occasion"], "everyday")
        self.assertEqual(debug["feelsLike"], 7)
        self.assertIn("warmth", debug)
        self.assertTrue(debug["appliedRules"])


class OccasionRuleTests(unittest.TestCase):
    def setUp(self):
        self.rule = CompatibilityRule()
        self.w = wardrobe()

    def variants(self, occasion, wthr=None):
        return self.rule.generateVariants(list(self.w.values()), wthr or weather(10, feels=9), occasion)

    def test_aliases(self):
        self.assertEqual(normalize_occasion("Торжественный"), Occasion.FORMAL)
        self.assertEqual(normalize_occasion("Прогулка / outdoor"), Occasion.OUTDOOR)
        self.assertEqual(normalize_occasion("что-то странное"), Occasion.EVERYDAY)
        self.assertEqual(normalize_occasion(None), Occasion.EVERYDAY)

    def test_formal_excludes_sneakers_shorts_jeans_hoodie_tshirt(self):
        outfits = self.variants("formal")
        self.assertTrue(outfits)
        for outfit in outfits:
            self.assertFalse(types(outfit) & {"Кроссовки", "Шорты", "Джинсы", "Худи", "Футболка"})

    def test_formal_prints_are_rejected(self):
        printed = make("Футболка с принтом", ItemPart.TOP, "белый", dressCode="formal")
        self.assertFalse(self.rule._itemFitsOccasion(printed, Occasion.FORMAL))

    def test_work_has_no_shorts_hoodie_sandals_and_prefers_smart(self):
        outfits = self.variants("work", weather(18, feels=18))
        self.assertTrue(outfits)
        for outfit in outfits:
            self.assertFalse(types(outfit) & {"Шорты", "Худи", "Сандалии", "Панама"})
        self.assertIn("Рубашка", types(outfits[0]))

    def test_sport_requires_sneakers_and_no_jeans_or_formal_shoes(self):
        runner = [
            make("Футболка", ItemPart.TOP, "белый"),
            make("Шорты", ItemPart.BOTTOM, "чёрный", material="polyester", dressCode="sport"),
            make("Кроссовки", ItemPart.SHOES, "белый"),
            make("Туфли", ItemPart.SHOES, "чёрный"),
            make("Джинсы", ItemPart.BOTTOM, "синий", material="denim"),
        ]
        outfits = self.rule.generateVariants(runner, weather(25, feels=25), "sport")
        self.assertTrue(outfits)
        for outfit in outfits:
            self.assertEqual(types(outfit) & {"Туфли", "Джинсы"}, set())
            self.assertIn("Кроссовки", types(outfit))

    def test_sport_without_sporty_bottoms_returns_nothing(self):
        casual = [self.w[key] for key in ("tshirt", "jeans", "pants", "sneakers")]
        self.assertEqual(self.rule.generateVariants(casual, weather(18, feels=18), "sport"), [])

    def test_outdoor_excludes_dress_shoes_and_blazer(self):
        for outfit in self.variants("outdoor"):
            self.assertFalse(types(outfit) & {"Туфли", "Блейзер", "Сандалии"})

    def test_occasion_changes_the_result(self):
        casual = {tuple(sorted(types(o))) for o in self.variants("everyday", weather(18, feels=18))}
        formal = {tuple(sorted(types(o))) for o in self.variants("formal", weather(18, feels=18))}
        self.assertTrue(casual and formal)
        self.assertNotEqual(casual, formal)


class CombinationRuleTests(unittest.TestCase):
    def setUp(self):
        self.rule = CompatibilityRule()

    def test_formality_must_stay_within_one_step_when_strict(self):
        tshirt = make("Футболка", ItemPart.TOP, "белый")
        jeans = make("Джинсы", ItemPart.BOTTOM, "синий", material="denim")
        oxford = make("Туфли", ItemPart.SHOES, "чёрный", dressCode="formal")
        result = self.rule.weatherCheck([tshirt, jeans, oxford], weather(22, feels=22))
        self.assertFalse(result.compatible)
        self.assertIn("формальност", result.reason)

    def test_more_than_three_main_colors_is_rejected(self):
        items = [
            make("Футболка", ItemPart.TOP, "белый"),
            make("Брюки", ItemPart.BOTTOM, "чёрный"),
            make("Кроссовки", ItemPart.SHOES, "коричневый"),
            make("Куртка", ItemPart.OUTERWEAR, "серый"),
        ]
        result = self.rule.check(items)
        self.assertFalse(result.compatible)
        self.assertIn("трёх основных цветов", result.reason)

    def test_two_accent_colors_fail_strict_but_one_accent_is_fine(self):
        base = [
            make("Брюки", ItemPart.BOTTOM, "чёрный"),
            make("Кроссовки", ItemPart.SHOES, "белый"),
        ]
        one = [make("Футболка", ItemPart.TOP, "красный"), *base]
        two = [make("Футболка", ItemPart.TOP, "красный"), *base[:1],
               make("Кроссовки", ItemPart.SHOES, "жёлтый")]
        profile = weather(22, feels=22)
        self.assertTrue(self.rule.weatherCheck(one, profile, strict=True).compatible)
        self.assertFalse(self.rule.weatherCheck(two, profile, strict=True).compatible)

    def test_denim_counts_as_neutral(self):
        items = [
            make("Футболка", ItemPart.TOP, "красный"),
            make("Джинсы", ItemPart.BOTTOM, "синий", material="denim"),
            make("Кроссовки", ItemPart.SHOES, "белый"),
        ]
        self.assertTrue(self.rule.weatherCheck(items, weather(22, feels=22), strict=True).compatible)

    def test_incompatible_color_pair(self):
        items = [
            make("Футболка", ItemPart.TOP, "красный"),
            make("Брюки", ItemPart.BOTTOM, "зелёный"),
            make("Кроссовки", ItemPart.SHOES, "белый"),
        ]
        self.assertIn("плохо сочетаются", self.rule.check(items).reason)

    def test_only_one_large_pattern(self):
        items = [
            make("Рубашка в клетку", ItemPart.TOP, "белый"),
            make("Юбка в полоску", ItemPart.BOTTOM, "чёрный"),
            make("Кроссовки", ItemPart.SHOES, "белый"),
        ]
        self.assertIn("паттерн", self.rule.check(items).reason)

    def test_winter_and_summer_materials_do_not_mix_with_shorts(self):
        items = [
            make("Футболка", ItemPart.TOP, "белый", material="cotton"),
            make("Шорты", ItemPart.BOTTOM, "бежевый", material="wool"),
            make("Кроссовки", ItemPart.SHOES, "белый"),
        ]
        self.assertIn("материал", self.rule.check(items).reason)


class CatalogTests(unittest.TestCase):
    def test_denim_jacket_is_outerwear_not_jeans(self):
        item = make("Джинсовая куртка", ItemPart.OUTERWEAR, "синий")
        self.assertEqual(catalog_entry_for(item)["key"], "jacket")

    def test_classification_ignores_style_field(self):
        item = make("Рубашка", ItemPart.TOP, "белый", style="streetwear")
        self.assertEqual(catalog_entry_for(item)["key"], "shirt")

    def test_unknown_type_falls_back_to_part(self):
        item = make("Нечто", ItemPart.SHOES, "белый")
        self.assertEqual(catalog_entry_for(item)["category"], "shoes")

    def test_catalog_entries_are_complete(self):
        from clima.outfit_rules import CLOTHING_CATALOG

        for key, entry in CLOTHING_CATALOG.items():
            with self.subTest(key=key):
                for field in ("category", "seasons", "formality", "warmth", "materials", "markers",
                              "compatible"):
                    self.assertIn(field, entry)
                self.assertTrue(1 <= entry["formality"] <= 5)


class BackendRegressionTests(unittest.TestCase):
    """Сценарии из tests/test_backend.py, воспроизведённые без БД."""

    def setUp(self):
        self.rule = CompatibilityRule()

    def test_plan_returns_three_variants_for_basic_wardrobe_at_18(self):
        items = [
            make("shirt", ItemPart.TOP, "white", material="cotton", minTemperature=-10),
            make("pants", ItemPart.BOTTOM, "black", material="cotton", minTemperature=-10),
            make("sneakers", ItemPart.SHOES, "white", material="cotton", minTemperature=-10),
            make("sweater", ItemPart.TOP, "blue", material="cotton", minTemperature=-10),
            make("skirt", ItemPart.BOTTOM, "beige", material="cotton", minTemperature=-10),
        ]
        self.assertEqual(len(self.rule.generateVariants(items, weather(18), "everyday")), 3)

    def test_dress_and_shoes_are_enough(self):
        dress = Item(id=1, userId=1, type="dress", color="black", seasons=ALL_SEASONS)
        shoes = Item(id=2, userId=1, type="sneakers", color="white", part=ItemPart.SHOES,
                     seasons=ALL_SEASONS)
        outfits = self.rule.generateVariants([dress, shoes], weather(18), "everyday")
        self.assertEqual(len(outfits), 1)
        self.assertEqual({item.id for item in outfits[0].items}, {1, 2})

    def test_top_and_bottom_without_shoes_give_nothing(self):
        items = [make("shirt", ItemPart.TOP, "white"), make("pants", ItemPart.BOTTOM, "black")]
        self.assertEqual(self.rule.generateVariants(items, weather(18)), [])

    def test_jacket_layers_in_cold_but_not_in_warm_weather(self):
        top = make("t-shirt", ItemPart.TOP, "white", material="cotton", minTemperature=-10)
        bottom = make("pants", ItemPart.BOTTOM, "black", material="cotton", minTemperature=-10)
        shoes = make("sneakers", ItemPart.SHOES, "white", material="leather", minTemperature=-10)
        jacket = make("jacket", ItemPart.OUTERWEAR, "black", material="denim", minTemperature=-10)
        scarf = make("scarf", ItemPart.ACCESSORY, "black", material="wool", minTemperature=-10)
        items = [top, bottom, shoes, jacket, scarf]
        warm = self.rule.generateVariants(items, weather(20))
        cold = self.rule.generateVariants(items, weather(5, conditions="снег"))
        self.assertTrue(warm)
        self.assertTrue(all(
            item.part not in (ItemPart.OUTERWEAR, ItemPart.ACCESSORY)
            for outfit in warm for item in outfit.items
        ))
        self.assertTrue(any(jacket in o.items and scarf in o.items for o in cold))

    def test_distinct_accessory_types_can_be_combined(self):
        items = [
            make("Футболка", ItemPart.TOP, "белый"),
            make("Брюки", ItemPart.BOTTOM, "чёрный"),
            make("Кроссовки", ItemPart.SHOES, "белый"),
            make("Сумка", ItemPart.ACCESSORY, "чёрный"),
            make("Шарф", ItemPart.ACCESSORY, "чёрный"),
            make("Шапка", ItemPart.ACCESSORY, "чёрный"),
        ]
        variants = self.rule.generateVariants(items, weather(5, conditions="снег"))
        self.assertTrue(any(all(a in o.items for a in items[3:]) for o in variants))
        self.assertTrue(all(self.rule.check(o.items).compatible for o in variants))


if __name__ == "__main__":
    unittest.main()

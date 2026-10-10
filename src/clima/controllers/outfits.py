from datetime import date, datetime
from itertools import product
from zoneinfo import ZoneInfo

from clima.errors import (
    AccessDeniedError,
    BadCombinationError,
    NotEnoughItemsError,
    NotFoundError,
    ValidationError,
)
from clima.models.entities import Item, Outfit, Preferences
from clima.models.entities.item import accessory_category_for_type, expected_part_for_type
from clima.models.enums import ItemPart, Season
from clima.models.value_objects import CheckResult, Messages, OutfitFilter, WeatherData
from clima.repositories.items import ItemsRepository
from clima.repositories.outfits import OutfitsRepository
from clima.repositories.users import UsersRepository
from clima.integrations.weather import WeatherService


class CompatibilityRule:
    maxVariants = 3
    colorAliases = {
        "red": {"red", "красный", "красная", "красное", "красные", "бордовый", "бордовая"},
        "green": {"green", "зеленый", "зелёный", "зеленая", "зелёная", "зеленое", "зелёное"},
        "orange": {"orange", "оранжевый", "оранжевая", "оранжевое"},
        "pink": {"pink", "розовый", "розовая", "розовое", "розовые"},
        "blue": {"blue", "синий", "синяя", "синее", "голубой", "голубая", "голубое"},
        "purple": {"purple", "фиолетовый", "фиолетовая", "фиолетовое"},
        "yellow": {"yellow", "желтый", "жёлтый", "желтая", "жёлтая", "желтое", "жёлтое"},
        "black": {"black", "черный", "чёрный", "черная", "чёрная", "черное", "чёрное"},
        "white": {"white", "белый", "белая", "белое"},
        "gray": {"gray", "grey", "серый", "серая", "серое"},
        "beige": {"beige", "бежевый", "бежевая", "бежевое"},
        "brown": {"brown", "коричневый", "коричневая", "коричневое"},
        "navy": {"navy", "темно-синий", "тёмно-синий"},
    }
    incompatiblePairs = {
        frozenset(("red", "green")),
        frozenset(("orange", "pink")),
        frozenset(("blue", "orange")),
        frozenset(("purple", "yellow")),
    }
    _neutrals = {"black", "white", "gray", "beige", "brown", "navy"}
    _dresses = {"dress", "jumpsuit", "комбинезон", "платье"}
    _scarves = ("шарф", "scarf")

    def check(self, items: list[Item]) -> CheckResult:
        available = [item for item in items if item.isAvailable()]
        if not available:
            return CheckResult(False, "Нет доступных вещей")
        one_pieces = [item for item in available if self._isOnePiece(item)]
        if len(one_pieces) > 1:
            return CheckResult(False, "В образе может быть только одно платье или комбинезон")
        tops = [
            item for item in available
            if item.part == ItemPart.TOP and not self._isOuterwear(item)
            and not self._isOnePiece(item)
        ]
        bottoms = [item for item in available if item.part == ItemPart.BOTTOM]
        shoes = [item for item in available if item.part == ItemPart.SHOES]
        outerwear = [item for item in available if self._isOuterwear(item)]
        if len(tops) > 1:
            return CheckResult(False, "В образе может быть только один верх")
        if len(bottoms) > 1:
            return CheckResult(False, "В образе может быть только один низ")
        if len(shoes) > 1:
            return CheckResult(False, "В образе может быть только одна пара обуви")
        if len(outerwear) > 1:
            return CheckResult(False, "В образе может быть только одна вещь верхней одежды")
        accessory_categories = [
            accessory_category_for_type(item.type)
            for item in available if item.part == ItemPart.ACCESSORY
        ]
        if len(accessory_categories) != len(set(accessory_categories)):
            return CheckResult(
                False, "Нельзя сочетать два аксессуара одного типа "
                "(например, две сумки, два шарфа или две шапки)"
            )
        if one_pieces:
            core = [item for item in available if not self._isOnePiece(item)]
            if any(
                item.part in (ItemPart.TOP, ItemPart.BOTTOM) and not self._isOuterwear(item)
                for item in core
            ):
                return CheckResult(False, "Платье или комбинезон нельзя сочетать с верхом или низом")
        else:
            tops = [
                item for item in available
                if item.part == ItemPart.TOP and not self._isOuterwear(item)
            ]
            bottoms = [item for item in available if item.part == ItemPart.BOTTOM]
            if not tops or not bottoms:
                return CheckResult(False, "Для образа нужны верх и низ или платье")
        if not shoes:
            return CheckResult(False, "Для полностью одетого образа нужна обувь")
        colors = [self._canonicalColor(item.color) for item in available]
        for index, first in enumerate(colors):
            for second in colors[index + 1:]:
                if first not in self._neutrals and second not in self._neutrals:
                    if frozenset((first, second)) in self.incompatiblePairs:
                        return CheckResult(
                            False, f"Цвета «{first}» и «{second}» плохо сочетаются"
                        )
        return CheckResult(True, "")

    def match(self, items: list[Item], weather: WeatherData, occasion: str) -> int:
        result = self.check(items)
        if not result.compatible:
            return 0
        score = 100
        for item in items:
            if not item.minTemperature <= weather.temperature <= item.maxTemperature:
                score -= 35
            if occasion and item.dressCode.casefold() not in {
                occasion.casefold(), "any", "casual", "повседневный",
            }:
                score -= 5
            if item.part == ItemPart.SHOES:
                score += 4
            elif item.part == ItemPart.ACCESSORY:
                score += 1
            if self._isOuterwear(item) and self._shouldSuggestOuterwear(weather):
                score += 5
            if self._isScarf(item) and self._shouldSuggestScarf(weather):
                score += 3
        conditions = weather.conditions.casefold()
        garments = " ".join(
            f"{item.type} {item.material} {item.dressCode}".casefold() for item in items
        )
        if any(word in conditions for word in ("дожд", "лив", "rain", "drizzle")):
            if any(word in garments for word in (
                "дождевик", "непромока", "водонепроница", "raincoat", "waterproof",
            )):
                score += 18
        if any(word in conditions for word in ("снег", "snow", "гроз", "thunder")):
            if any(word in garments for word in (
                "зим", "утепл", "пуховик", "snow", "winter",
            )):
                score += 8
        if any(word in conditions for word in ("жара", "ясно", "clear", "sun")):
            if any(word in garments for word in (
                "лён", "лен ", "хлопок", "cotton", "linen", "light",
            )):
                score += 5
        return max(score, 1)

    def generateVariants(
        self, items: list[Item], weather: WeatherData, occasion: str = "everyday",
        preferences: Preferences | None = None,
        season: Season | None = None,
    ) -> list[Outfit]:
        season = season or self._seasonFor(weather.date)
        candidates = [
            item for item in items
            if item.isAvailable()
            and item.minTemperature <= weather.temperature <= item.maxTemperature
            and (not item.seasons or season in item.seasons)
        ]
        tops = [item for item in candidates if item.part == ItemPart.TOP]
        outerwear = [item for item in candidates if self._isOuterwear(item)][:3]
        bottoms = [item for item in candidates if item.part == ItemPart.BOTTOM]
        dresses = [item for item in candidates if self._isOnePiece(item)]
        tops = [
            item for item in tops
            if not self._isOnePiece(item) and not self._isOuterwear(item)
        ]
        bottoms = [item for item in bottoms if not self._isOnePiece(item)]
        shoes = [item for item in candidates if item.part == ItemPart.SHOES][:3]
        accessory_groups: dict[str, list[Item]] = {}
        for item in candidates:
            if item.part != ItemPart.ACCESSORY:
                continue
            if self._isScarf(item) and not self._shouldSuggestScarf(weather):
                continue
            category = accessory_category_for_type(item.type)
            if category not in accessory_groups and len(accessory_groups) == 3:
                continue
            accessory_groups.setdefault(category, []).append(item)
        accessory_choices = [
            [None, *group[:3]] for group in accessory_groups.values()
        ]
        outerwear = outerwear if self._shouldSuggestOuterwear(weather) else []
        combinations: list[tuple[Item, ...]] = []
        core_combinations = [(dress,) for dress in dresses]
        core_combinations.extend(product(tops, bottoms))
        for core in core_combinations:
            for shoe in shoes:
                for layer in [None, *outerwear]:
                    for accessory_selection in self._accessorySelections(accessory_choices):
                        extras = tuple(
                            item for item in (shoe, layer, *accessory_selection)
                            if item is not None
                        )
                        combinations.append((*core, *extras))
        scored = [
            (
                self.match(list(items_set), weather, occasion)
                + self._preferenceScore(list(items_set), preferences),
                items_set,
            )
            for items_set in combinations
            if self.check(list(items_set)).compatible
        ]
        scored.sort(key=lambda entry: (-entry[0], tuple(item.id for item in entry[1])))
        variants: list[Outfit] = []
        seen: set[tuple[int, ...]] = set()
        for _, matched in scored:
            ids = tuple(item.id for item in matched)
            if ids in seen:
                continue
            seen.add(ids)
            variants.append(Outfit(
                date=weather.date, place=weather.place, occasion=occasion,
                items=list(matched),
            ))
            if len(variants) == self.maxVariants:
                break
        return variants

    @staticmethod
    def _preferenceScore(items: list[Item], preferences: Preferences | None) -> int:
        if preferences is None:
            return 0
        colors = {
            CompatibilityRule._canonicalColor(value)
            for value in preferences.colors.split(",") if value.strip()
        }
        styles = {value.strip().casefold() for value in preferences.style.split(",") if value.strip()}
        silhouettes = {
            value.strip().casefold()
            for value in preferences.bodyFeatures.split(",") if value.strip()
        }
        return sum(
            (12 if CompatibilityRule._canonicalColor(item.color) in colors else 0)
            + (10 if item.style.casefold() in styles else 0)
            + (5 if item.silhouette.casefold() in silhouettes else 0)
            for item in items
        )

    @classmethod
    def _isOnePiece(cls, item: Item) -> bool:
        return item.part == ItemPart.ONE_PIECE or item.type.casefold() in cls._dresses

    @staticmethod
    def _isOuterwear(item: Item) -> bool:
        return (
            item.part == ItemPart.OUTERWEAR
            or expected_part_for_type(item.type) == ItemPart.OUTERWEAR
        )

    @classmethod
    def _isScarf(cls, item: Item) -> bool:
        normalized = item.type.casefold()
        return any(marker in normalized for marker in cls._scarves)

    @staticmethod
    def _accessorySelections(choices: list[list[Item | None]]) -> list[tuple[Item | None, ...]]:
        return list(product(*choices)) if choices else [()]

    @staticmethod
    def _shouldSuggestOuterwear(weather: WeatherData) -> bool:
        conditions = weather.conditions.casefold()
        return weather.temperature <= 15 or any(
            marker in conditions for marker in ("дожд", "лив", "rain", "drizzle", "снег", "snow")
        )

    @staticmethod
    def _shouldSuggestScarf(weather: WeatherData) -> bool:
        conditions = weather.conditions.casefold()
        return weather.temperature <= 8 or any(
            marker in conditions for marker in ("снег", "snow", "мороз", "freez")
        )

    @staticmethod
    def _seasonFor(day: date) -> Season:
        if day.month in (12, 1, 2):
            return Season.WINTER
        if day.month in (3, 4, 5):
            return Season.SPRING
        if day.month in (6, 7, 8):
            return Season.SUMMER
        return Season.AUTUMN

    @classmethod
    def _canonicalColor(cls, value: str) -> str:
        normalized = value.strip().casefold()
        for canonical, aliases in cls.colorAliases.items():
            if normalized in aliases:
                return canonical
        return normalized


class OutfitController:
    def __init__(
        self,
        itemsRepository: ItemsRepository,
        outfitsRepository: OutfitsRepository,
        rule: CompatibilityRule,
        weatherService: WeatherService,
        usersRepository: UsersRepository,
    ):
        self.itemsRepository = itemsRepository
        self.outfitsRepository = outfitsRepository
        self.rule = rule
        self.weatherService = weatherService
        self.usersRepository = usersRepository

    def getTodayOutfits(self, userId: int, location: str | None = None) -> list[Outfit]:
        user = self.usersRepository.findById(userId)
        place = (location or (user.location if user else "")).strip()
        if not place:
            raise ValidationError("Укажите место в запросе или профиле")
        selected_date = (
            datetime.now(ZoneInfo(user.settings.timeZone)).date()
            if user is not None
            else date.today()
        )
        filter = OutfitFilter(selected_date, place)
        weather = self.weatherService.getForecast(filter.place, filter.date)
        cached = self.outfitsRepository.findByDate(userId, filter.date, filter.place)
        available = self.itemsRepository.findAvailableByUser(userId)
        if cached and self._isCurrent(cached, available, weather):
            return cached[:self.rule.maxVariants]
        outfits = self._generate(userId, filter, useCache=True, forecast=weather)
        if not outfits:
            self._raiseIfWardrobeIncomplete(userId)
        return outfits

    def getTodayOutfit(self, userId: int) -> Outfit:
        outfits = self.getTodayOutfits(userId)
        if not outfits:
            status = self.getWardrobeStatus(userId)
            raise NotEnoughItemsError(
                Messages.NOT_ENOUGH_ITEMS,
                status["missing"] if not status["is_complete"] else None,
                status["have"] if not status["is_complete"] else None,
            )
        return outfits[0]

    def planOutfit(self, userId: int, filter: OutfitFilter) -> list[Outfit]:
        outfits = self._generate(userId, filter)
        if not outfits:
            self._raiseIfWardrobeIncomplete(userId)
        return outfits

    def selectOutfit(self, userId: int, outfitId: int) -> Outfit:
        outfit = self.getOutfit(userId, outfitId)
        outfit.setSelected(True)
        self.outfitsRepository.update(outfit)
        return outfit

    def getOutfit(self, userId: int, outfitId: int) -> Outfit:
        outfit = self.outfitsRepository.findById(outfitId)
        if outfit is None:
            raise NotFoundError("Аутфит не найден")
        if not outfit.belongsTo(userId):
            raise AccessDeniedError("Нет доступа к объекту")
        return outfit

    def getOutfitHistory(self, userId: int) -> list[Outfit]:
        return self.outfitsRepository.findHistoryByUser(userId)

    def getOutfitsToRate(self, userId: int) -> list[Outfit]:
        return self.outfitsRepository.findToRateByUser(userId)

    def createOutfitFromItems(self, userId: int, itemIds: list[int]) -> Outfit:
        if len(itemIds) < 1 or len(set(itemIds)) != len(itemIds):
            raise ValidationError("Выберите одну или несколько разных вещей")
        items = self.itemsRepository.findByIds(itemIds)
        if len(items) != len(itemIds):
            raise NotFoundError("Одна или несколько вещей не найдены")
        if any(not item.belongsTo(userId) for item in items):
            raise AccessDeniedError("Нет доступа к объекту")
        if any(not item.isAvailable() for item in items):
            raise ValidationError("Нельзя использовать удалённые вещи или вещи в стирке")
        result = self.rule.check(items)
        if not result.compatible:
            raise BadCombinationError(result.reason or Messages.BAD_COMBINATION)
        user = self.usersRepository.findById(userId)
        outfit = Outfit(
            userId=userId, date=date.today(), place=user.location if user else "",
            occasion="everyday", items=items,
        )
        self.outfitsRepository.create(outfit)
        return outfit

    def getWardrobe(self, userId: int) -> list[Item]:
        return self.itemsRepository.findByUser(userId)

    def getWardrobeStatus(self, userId: int) -> dict:
        have = {
            "top": 0,
            "outerwear": 0,
            "bottom": 0,
            "shoes": 0,
            "bag": 0,
            "hat": 0,
            "accessories": 0,
            "one_piece": 0,
        }
        for item in self.itemsRepository.findAvailableByUser(userId):
            if self.rule._isOnePiece(item):
                have["one_piece"] += 1
            elif self.rule._isOuterwear(item):
                have["outerwear"] += 1
            elif item.part == ItemPart.TOP:
                have["top"] += 1
            elif item.part == ItemPart.BOTTOM:
                have["bottom"] += 1
            elif item.part == ItemPart.SHOES:
                have["shoes"] += 1
            elif item.part == ItemPart.ACCESSORY:
                category = accessory_category_for_type(item.type)
                if category == "bag":
                    have["bag"] += 1
                elif category == "headwear":
                    have["hat"] += 1
                else:
                    have["accessories"] += 1
        missing = []
        if not (have["top"] or have["one_piece"]):
            missing.append("top")
        if not (have["bottom"] or have["one_piece"]):
            missing.append("bottom")
        if not have["shoes"]:
            missing.append("shoes")
        return {"have": have, "missing": missing, "is_complete": not missing}

    def _raiseIfWardrobeIncomplete(self, userId: int) -> None:
        status = self.getWardrobeStatus(userId)
        if not status["is_complete"]:
            raise NotEnoughItemsError(
                Messages.NOT_ENOUGH_ITEMS, status["missing"], status["have"]
            )

    def validateReplacement(self, items: list[Item]) -> None:
        result = self.rule.check(items)
        if not result.compatible:
            raise BadCombinationError(result.reason or Messages.BAD_COMBINATION)

    def _generate(
        self, userId: int, filter: OutfitFilter, useCache: bool = False,
        forecast: WeatherData | None = None,
    ) -> list[Outfit]:
        weather = forecast or self.weatherService.getForecast(filter.place, filter.date)
        if filter.temperature is not None:
            weather = WeatherData(
                place=weather.place, date=weather.date,
                temperature=filter.temperature, conditions=weather.conditions,
            )
        items = self.itemsRepository.findAvailableByUser(userId)
        if not items:
            self._raiseIfWardrobeIncomplete(userId)
            raise NotEnoughItemsError(Messages.NOT_ENOUGH_ITEMS)
        user = self.usersRepository.findById(userId)
        variants = self.rule.generateVariants(
            items, weather, filter.occasion, user.preferences if user else None, filter.season
        )
        if not variants:
            if useCache:
                self.outfitsRepository.deleteGeneratedByDate(userId, filter.date, filter.place)
            return []
        if useCache:
            self.outfitsRepository.deleteGeneratedByDate(userId, filter.date, filter.place)
        for outfit in variants:
            outfit.userId = userId
            outfit.place = filter.place
        self.outfitsRepository.save(variants)
        return variants

    def _isCurrent(
        self, outfits: list[Outfit], available: list[Item], weather: WeatherData
    ) -> bool:
        indexed = {item.id: item for item in available}
        for outfit in outfits:
            if not outfit.items:
                return False
            if any(item.id not in indexed for item in outfit.items):
                return False
            current_items = [indexed[item.id] for item in outfit.items]
            if not self.rule.check(current_items).compatible:
                return False
            if not self.rule._shouldSuggestOuterwear(weather) and any(
                self.rule._isOuterwear(item) for item in current_items
            ):
                return False
            if not self.rule._shouldSuggestScarf(weather) and any(
                self.rule._isScarf(item) for item in current_items
            ):
                return False
        season = self.rule._seasonFor(weather.date)
        weather_items = [
            item for item in available
            if item.minTemperature <= weather.temperature <= item.maxTemperature
            and (not item.seasons or season in item.seasons)
        ]
        if self.rule._shouldSuggestOuterwear(weather):
            available_outerwear = any(self.rule._isOuterwear(item) for item in weather_items)
            suggested_outerwear = any(
                self.rule._isOuterwear(item) for outfit in outfits for item in outfit.items
            )
            if available_outerwear and not suggested_outerwear:
                return False
        if self.rule._shouldSuggestScarf(weather):
            available_scarf = any(self.rule._isScarf(item) for item in weather_items)
            suggested_scarf = any(
                self.rule._isScarf(item) for outfit in outfits for item in outfit.items
            )
            if available_scarf and not suggested_scarf:
                return False
        return True

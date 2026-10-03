from datetime import date
from itertools import product

from clima.errors import (
    AccessDeniedError,
    BadCombinationError,
    NotEnoughItemsError,
    NotFoundError,
    ValidationError,
)
from clima.models.entities import Item, Outfit, Preferences
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

    def check(self, items: list[Item]) -> CheckResult:
        available = [item for item in items if item.isAvailable()]
        if not available:
            return CheckResult(False, "Нет доступных вещей")
        if len(available) == 1 and available[0].type.casefold() in self._dresses:
            return CheckResult(True, "")
        tops = [item for item in available if item.part == ItemPart.TOP]
        bottoms = [item for item in available if item.part == ItemPart.BOTTOM]
        if not tops or not bottoms:
            return CheckResult(False, "Для комплекта нужны верх и низ или платье")
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
        bottoms = [item for item in candidates if item.part == ItemPart.BOTTOM]
        dresses = [item for item in candidates if item.type.casefold() in self._dresses]
        combinations: list[tuple[Item, ...]] = [(dress,) for dress in dresses]
        combinations.extend(product(tops, bottoms))
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
        filter = OutfitFilter(date.today(), place)
        cached = self.outfitsRepository.findByDate(userId, filter.date, filter.place)
        if cached and self._isCurrent(cached, self.itemsRepository.findAvailableByUser(userId)):
            return cached[:self.rule.maxVariants]
        return self._generate(userId, filter, useCache=True)

    def getTodayOutfit(self, userId: int) -> Outfit:
        outfits = self.getTodayOutfits(userId)
        if not outfits:
            raise NotEnoughItemsError(Messages.NOT_ENOUGH_ITEMS)
        return outfits[0]

    def planOutfit(self, userId: int, filter: OutfitFilter) -> list[Outfit]:
        return self._generate(userId, filter)

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

    def validateReplacement(self, items: list[Item]) -> None:
        result = self.rule.check(items)
        if not result.compatible:
            raise BadCombinationError(result.reason or Messages.BAD_COMBINATION)

    def _generate(
        self, userId: int, filter: OutfitFilter, useCache: bool = False
    ) -> list[Outfit]:
        weather = self.weatherService.getForecast(filter.place, filter.date)
        if filter.temperature is not None:
            weather = WeatherData(
                place=weather.place, date=weather.date,
                temperature=filter.temperature, conditions=weather.conditions,
            )
        items = self.itemsRepository.findAvailableByUser(userId)
        if len(items) < 2:
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

    def _isCurrent(self, outfits: list[Outfit], available: list[Item]) -> bool:
        indexed = {item.id: item for item in available}
        for outfit in outfits:
            if not outfit.items:
                return False
            if any(item.id not in indexed for item in outfit.items):
                return False
            current_items = [indexed[item.id] for item in outfit.items]
            if not self.rule.check(current_items).compatible:
                return False
        return True

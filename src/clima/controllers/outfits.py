from datetime import date, datetime
from zoneinfo import ZoneInfo

from clima.errors import (
    AccessDeniedError,
    BadCombinationError,
    NotEnoughItemsError,
    NotFoundError,
    ValidationError,
)
from clima.models.entities import Item, Outfit
from clima.models.entities.item import accessory_category_for_type
from clima.models.enums import ItemPart
from clima.models.value_objects import Messages, OutfitFilter, WeatherData
from clima.outfit_rules import CompatibilityRule
from clima.repositories.items import ItemsRepository
from clima.repositories.outfits import OutfitsRepository
from clima.repositories.users import UsersRepository
from clima.integrations.weather import WeatherService

__all__ = ["CompatibilityRule", "OutfitController"]


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

    def getTodayOutfits(
        self, userId: int, location: str | None = None,
        latitude: float | None = None, longitude: float | None = None,
    ) -> list[Outfit]:
        user = self.usersRepository.findById(userId)
        place = (location or (user.location if user else "")).strip()
        if not place:
            raise ValidationError("Укажите место в запросе или профиле")
        selected_date = (
            datetime.now(ZoneInfo(user.settings.timeZone)).date()
            if user is not None
            else date.today()
        )
        filter = OutfitFilter(selected_date, place, latitude=latitude, longitude=longitude)
        weather = self.weatherService.getForecast(
            filter.place, filter.date,
            latitude=filter.latitude, longitude=filter.longitude,
        )
        cached = self.outfitsRepository.findByDate(userId, filter.date, filter.place)
        available = self.itemsRepository.findAvailableByUser(userId)
        if cached and self._isCurrent(cached, available, weather):
            for outfit in cached[:self.rule.maxVariants]:
                outfit.debug = self.rule.explain(
                    outfit.items, weather, filter.occasion,
                    self.rule.match(outfit.items, weather, filter.occasion),
                )
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
            items = self.itemsRepository.findAvailableByUser(userId)
            user = self.usersRepository.findById(userId)
            weather = self.weatherService.getForecast(
                filter.place, filter.date,
                latitude=filter.latitude, longitude=filter.longitude,
            )
            if filter.temperature is not None:
                weather = WeatherData(
                    place=weather.place, date=weather.date,
                    temperature=filter.temperature, conditions=weather.conditions,
                    feelsLike=filter.temperature, windSpeed=weather.windSpeed,
                    humidity=weather.humidity, precipitation=weather.precipitation,
                    uvIndex=weather.uvIndex, latitude=weather.latitude,
                    longitude=weather.longitude, source=weather.source,
                )
            reason = self.rule.explainEmpty(
                items, weather, filter.occasion,
                user.preferences if user else None, filter.season,
            )
            raise NotEnoughItemsError(reason)
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
        weather = forecast or self.weatherService.getForecast(
            filter.place, filter.date,
            latitude=filter.latitude, longitude=filter.longitude,
        )
        if filter.temperature is not None:
            weather = WeatherData(
                place=weather.place, date=weather.date,
                temperature=filter.temperature, conditions=weather.conditions,
                feelsLike=filter.temperature, windSpeed=weather.windSpeed,
                humidity=weather.humidity, precipitation=weather.precipitation,
                uvIndex=weather.uvIndex, latitude=weather.latitude,
                longitude=weather.longitude, source=weather.source,
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
            if not outfit.debug:
                outfit.debug = self.rule.explain(
                    outfit.items, weather, filter.occasion,
                    self.rule.match(outfit.items, weather, filter.occasion),
                )
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
            # Образы, сохранённые до обновления правил (или при другой погоде), пересобираем.
            if not self.rule.weatherCheck(
                current_items, weather, outfit.occasion or "everyday",
            ).compatible:
                return False
            if not self.rule._shouldSuggestOuterwear(weather) and any(
                self.rule._isOuterwear(item) for item in current_items
            ):
                return False
            if not self.rule._shouldSuggestScarf(weather) and any(
                self.rule._isScarf(item) for item in current_items
            ):
                return False
        season = self.rule._seasonFor(weather.date, weather.latitude)
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

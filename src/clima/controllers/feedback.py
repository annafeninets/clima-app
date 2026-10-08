from psycopg.errors import ForeignKeyViolation, UniqueViolation

from clima.errors import (
    AccessDeniedError,
    AlreadyFavoriteError,
    NotFoundError,
    ValidationError,
)
from clima.models.entities import Favorite, Item, Outfit
from clima.repositories.favorites import FavoritesRepository
from clima.repositories.items import ItemsRepository
from clima.repositories.outfits import OutfitsRepository
from clima.controllers.outfits import CompatibilityRule


class FeedbackController:
    def __init__(
        self,
        favoritesRepository: FavoritesRepository,
        outfitsRepository: OutfitsRepository,
        itemsRepository: ItemsRepository,
        rule: CompatibilityRule,
    ):
        self.favoritesRepository = favoritesRepository
        self.outfitsRepository = outfitsRepository
        self.itemsRepository = itemsRepository
        self.rule = rule

    def getOutfitsToRate(self, userId: int) -> list[Outfit]:
        return [
            outfit for outfit in self.outfitsRepository.findByUser(userId)
            if outfit.selected and outfit.rating == 0
        ]

    def rateOutfit(self, userId: int, outfitId: int, score: int) -> None:
        if isinstance(score, bool) or not 1 <= score <= 5:
            raise ValidationError("Оценка должна быть целым числом от 1 до 5")
        outfit = self._ownedOutfit(userId, outfitId)
        if not outfit.selected:
            raise ValidationError("Сначала отметьте аутфит как выбранный")
        outfit.setRating(score)
        self.outfitsRepository.update(outfit)

    def addFavorite(self, userId: int, outfitId: int) -> Favorite:
        self._ownedOutfit(userId, outfitId)
        if self.favoritesRepository.exists(userId, outfitId):
            raise AlreadyFavoriteError("Аутфит уже добавлен в избранное")
        favorite = Favorite(userId=userId, outfitId=outfitId)
        try:
            self.favoritesRepository.add(favorite)
        except UniqueViolation as error:
            raise AlreadyFavoriteError("Аутфит уже добавлен в избранное") from error
        except ForeignKeyViolation as error:
            raise NotFoundError("Аутфит не найден") from error
        return favorite

    def removeFavorite(self, userId: int, favoriteId: int) -> None:
        favorite = self.favoritesRepository.findById(favoriteId)
        if favorite is None:
            raise NotFoundError("Избранное не найдено")
        if not favorite.belongsTo(userId):
            raise AccessDeniedError("Нет доступа к объекту")
        self.favoritesRepository.delete(favoriteId)

    def getFavorites(self, userId: int) -> list[Favorite]:
        return self.favoritesRepository.findByUser(userId)

    def getFavoriteOutfit(self, userId: int, favoriteId: int) -> Outfit:
        favorite = self._ownedFavorite(userId, favoriteId)
        return self._ownedOutfit(userId, favorite.outfitId)

    def updateFavoriteOutfit(
        self, userId: int, favoriteId: int, itemId: int, newItem: Item
    ) -> Outfit:
        favorite = self._ownedFavorite(userId, favoriteId)
        outfit = self._ownedOutfit(userId, favorite.outfitId)
        if not any(item.id == itemId for item in outfit.items):
            raise NotFoundError("Вещь не входит в аутфит")
        replacement = self.itemsRepository.findById(newItem.id)
        if replacement is None or replacement.deleted:
            raise NotFoundError("Вещь для замены не найдена")
        if not replacement.belongsTo(userId):
            raise AccessDeniedError("Нет доступа к объекту")
        if not replacement.isAvailable():
            raise ValidationError("Нельзя использовать вещь, находящуюся в стирке")
        original = next(item for item in outfit.items if item.id == itemId)
        if replacement.part != original.part:
            raise ValidationError("Нельзя заменить верх нижней частью или наоборот")
        outfit.replaceItem(itemId, replacement)
        check = self.rule.check(outfit.items)
        if not check.compatible:
            raise ValidationError(check.reason)
        self.outfitsRepository.update(outfit)
        return outfit

    def _ownedFavorite(self, userId: int, favoriteId: int) -> Favorite:
        favorite = self.favoritesRepository.findById(favoriteId)
        if favorite is None:
            raise NotFoundError("Избранное не найдено")
        if not favorite.belongsTo(userId):
            raise AccessDeniedError("Нет доступа к объекту")
        return favorite

    def _ownedOutfit(self, userId: int, outfitId: int) -> Outfit:
        outfit = self.outfitsRepository.findById(outfitId)
        if outfit is None:
            raise NotFoundError("Аутфит не найден")
        if not outfit.belongsTo(userId):
            raise AccessDeniedError("Нет доступа к объекту")
        return outfit

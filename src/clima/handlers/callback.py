from clima.controllers.feedback import FeedbackController
from clima.controllers.outfits import OutfitController
from clima.controllers.users import AuthController
from clima.controllers.wardrobe import WardrobeController
from clima.errors import NotFoundError, ValidationError
from clima.handlers.base import Handler
from clima.handlers.helpers import item_from_data, parse_photo
from clima.models.enums import Actions
from clima.models.value_objects import Request, Response


class CallbackHandler(Handler):
    def __init__(
        self,
        authController: AuthController,
        outfitController: OutfitController,
        feedbackController: FeedbackController,
        wardrobeController: WardrobeController,
    ):
        super().__init__(authController)
        self.outfitController = outfitController
        self.feedbackController = feedbackController
        self.wardrobeController = wardrobeController

    def handle(self, request: Request) -> Response:
        userId = self.authenticate(request)
        return self.handleCallback(request.action, [request, userId])

    def handleCallback(self, action: str, args: list) -> Response:
        if args and not isinstance(args[0], Request):
            return self._handleAction(action, args)
        request, userId = args
        path, method, body = request.path, request.method, request.body
        if path == "/wardrobe/status" and method == "GET":
            return Response.ok(self.outfitController.getWardrobeStatus(userId))
        if path == "/wardrobe" and method == "GET":
            return Response.ok(self.wardrobeController.getWardrobe(userId))
        if path.startswith("/wardrobe/items/"):
            itemId = _path_id(path, "/wardrobe/items/")
            if path.endswith("/photo") and method == "GET":
                photo = self.wardrobeController.getItemPhoto(userId, itemId)
                return Response(
                    True, data=photo,
                    contentType=self.wardrobeController.getItemPhotoContentType(userId, itemId),
                )
            if path.endswith("/photo") and method == "PUT":
                item = self.wardrobeController.updateItemPhoto(
                    userId, itemId, parse_photo(body.get("photo"))
                )
                return Response.ok(item, "Фото вещи обновлено")
            if path.endswith("/laundry") and method == "PUT":
                value = body.get("value")
                if not isinstance(value, bool):
                    raise ValidationError("Поле value должно быть boolean")
                self.wardrobeController.markInLaundry(userId, itemId, value)
                return Response.ok(message="Статус вещи обновлён")
            if method == "GET":
                return Response.ok(self.wardrobeController.getItem(userId, itemId))
            if method == "PUT":
                current = self.wardrobeController.getItem(userId, itemId)
                data = item_from_data(body, userId, current)
                return Response.ok(
                    self.wardrobeController.updateItem(userId, itemId, data),
                    "Вещь обновлена",
                )
            if method == "DELETE":
                self.wardrobeController.deleteItem(userId, itemId)
                return Response.ok(message="Вещь удалена")
        if path == "/favorites" and method == "GET":
            return Response.ok(self.feedbackController.getFavorites(userId))
        if path == "/favorites" and method == "POST":
            outfitId = _integer(body, "outfitId")
            return Response.ok(
                self.feedbackController.addFavorite(userId, outfitId),
                "Аутфит добавлен в избранное",
            )
        if path == "/favorites/compose" and method == "POST":
            raw_ids = body.get("itemIds")
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ValidationError("Выберите вещи для аутфита")
            try:
                itemIds = [int(value) for value in raw_ids]
            except (ValueError, TypeError) as error:
                raise ValidationError("Некорректный список вещей") from error
            outfit = self.outfitController.createOutfitFromItems(userId, itemIds)
            favorite = self.feedbackController.addFavorite(userId, outfit.id)
            return Response.ok(
                {"outfit": outfit, "favorite": favorite},
                "Аутфит создан и добавлен в избранное",
            )
        if path.startswith("/favorites/"):
            favoriteId = _path_id(path, "/favorites/")
            if "/items/" in path and method == "PUT":
                target_item_id = _path_id(path.split("/items/", 1)[1], "")
                try:
                    replacement_id = int(body["itemId"])
                except (KeyError, ValueError, TypeError) as error:
                    raise ValidationError("Укажите itemId для замены") from error
                from clima.models.entities import Item

                outfit = self.feedbackController.updateFavoriteOutfit(
                    userId, favoriteId, target_item_id, Item(id=replacement_id)
                )
                return Response.ok(outfit, "Аутфит обновлён")
            if method == "GET":
                return Response.ok(self.feedbackController.getFavoriteOutfit(userId, favoriteId))
            if method == "DELETE":
                self.feedbackController.removeFavorite(userId, favoriteId)
                return Response.ok(message="Удалено из избранного")
        if path.startswith("/outfits/") and path.endswith("/rating") and method == "PUT":
            outfitId = _path_id(path, "/outfits/")
            self.feedbackController.rateOutfit(userId, outfitId, _integer(body, "score"))
            return Response.ok(message="Оценка учтена")
        raise ValidationError("Неизвестное действие")

    def _handleAction(self, action: str, args: list) -> Response:
        if action == Actions.RATE and len(args) == 3:
            userId, outfitId, score = (_integer_value(value) for value in args)
            self.feedbackController.rateOutfit(userId, outfitId, score)
            return Response.ok(message="Оценка учтена")
        if action in (Actions.ADD_FAVORITE, Actions.SAVE) and len(args) == 2:
            userId, outfitId = (_integer_value(value) for value in args)
            return Response.ok(self.feedbackController.addFavorite(userId, outfitId))
        if action == Actions.REMOVE_FAVORITE and len(args) == 2:
            userId, favoriteId = (_integer_value(value) for value in args)
            self.feedbackController.removeFavorite(userId, favoriteId)
            return Response.ok()
        if action == Actions.OPEN_FAVORITE and len(args) == 2:
            userId, favoriteId = (_integer_value(value) for value in args)
            return Response.ok(self.feedbackController.getFavoriteOutfit(userId, favoriteId))
        if action == Actions.REPLACE_ITEM and len(args) == 4:
            userId, favoriteId, itemId, replacement = args
            from clima.models.entities import Item

            item = replacement if isinstance(replacement, Item) else Item(id=_integer_value(replacement))
            return Response.ok(self.feedbackController.updateFavoriteOutfit(
                _integer_value(userId), _integer_value(favoriteId),
                _integer_value(itemId), item
            ))
        if action == Actions.SELECT_OUTFIT and len(args) == 2:
            return Response.ok(self.outfitController.selectOutfit(
                _integer_value(args[0]), _integer_value(args[1])
            ))
        if action == Actions.SELECT_ITEMS and len(args) == 2:
            outfit = self.outfitController.createOutfitFromItems(
                _integer_value(args[0]), [_integer_value(value) for value in args[1]]
            )
            favorite = self.feedbackController.addFavorite(_integer_value(args[0]), outfit.id)
            return Response.ok({"outfit": outfit, "favorite": favorite})
        if action == Actions.MARK_LAUNDRY and len(args) == 3:
            userId, itemId, value = args
            if not isinstance(value, bool):
                raise ValidationError("Значение статуса стирки должно быть boolean")
            self.wardrobeController.markInLaundry(
                _integer_value(userId), _integer_value(itemId), value
            )
            return Response.ok()
        if action == Actions.DELETE_ITEM and len(args) == 2:
            self.wardrobeController.deleteItem(_integer_value(args[0]), _integer_value(args[1]))
            return Response.ok()
        if action == Actions.EDIT_ITEM and len(args) == 3:
            userId, itemId, data = args
            current = self.wardrobeController.getItem(
                _integer_value(userId), _integer_value(itemId)
            )
            item = item_from_data(data, _integer_value(userId), current)
            return Response.ok(self.wardrobeController.updateItem(
                _integer_value(userId), _integer_value(itemId), item
            ))
        if action == Actions.EDIT_PHOTO and len(args) == 3:
            return Response.ok(self.wardrobeController.updateItemPhoto(
                _integer_value(args[0]), _integer_value(args[1]), bytes(args[2])
            ))
        raise ValidationError("Неизвестное действие")


def _integer(body: dict, key: str) -> int:
    value = body.get(key)
    if isinstance(value, bool):
        raise ValidationError(f"Поле {key} должно быть целым числом")
    return _integer_value(value, f"Поле {key} должно быть целым числом")


def _integer_value(value, message: str = "Ожидалось целое число") -> int:
    if isinstance(value, bool):
        raise ValidationError(message)
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(message) from error


def _path_id(path: str, prefix: str) -> int:
    try:
        return int(path.removeprefix(prefix).split("/", 1)[0])
    except ValueError as error:
        raise ValidationError("Некорректный идентификатор") from error

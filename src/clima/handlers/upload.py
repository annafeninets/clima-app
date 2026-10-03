from clima.controllers.users import AuthController
from clima.controllers.wardrobe import WardrobeController
from clima.errors import ValidationError
from clima.handlers.base import Handler
from clima.handlers.helpers import item_from_data, parse_photo
from clima.models.enums import Actions
from clima.models.value_objects import Request, Response


class UploadHandler(Handler):
    def __init__(self, authController: AuthController, wardrobeController: WardrobeController):
        super().__init__(authController)
        self.wardrobeController = wardrobeController

    def handle(self, request: Request) -> Response:
        userId = self.authenticate(request)
        return self.handleUpload(request.action, [request, userId])

    def handleUpload(self, action: str, args: list) -> Response:
        if args and not isinstance(args[0], Request):
            return self._handleAction(action, args)
        request, userId = args
        if action == "POST /wardrobe/items":
            item = self.wardrobeController.addItem(userId, parse_photo(request.body.get("photo")))
            return Response.ok(item, "Заполните карточку вещи")
        if action == "PUT /wardrobe/items/draft":
            data = request.body
            card = data.get("item", data)
            if not isinstance(card, dict):
                raise ValidationError("Карточка вещи должна быть объектом")
            _validate_card_fields(card)
            item = item_from_data(card, userId)
            item.validate()
            photo = data.get("photo")
            if not isinstance(photo, str) or not photo:
                raise ValidationError("Укажите фотографию вещи")
            if self.wardrobeController.photoStorage.belongsTo(userId, photo):
                item.setPhoto(photo)
            else:
                item.setPhoto(self.wardrobeController.photoStorage.save(
                    userId, parse_photo(photo)
                ))
            return Response.ok(
                self.wardrobeController.confirmItem(userId, item), "Вещь сохранена"
            )
        raise ValidationError("Неизвестная операция загрузки")

    def _handleAction(self, action: str, args: list) -> Response:
        if action == Actions.EDIT_PHOTO and len(args) == 3:
            userId, itemId, photo = args
            try:
                return Response.ok(self.wardrobeController.updateItemPhoto(
                    int(userId), int(itemId), bytes(photo)
                ))
            except (ValueError, TypeError) as error:
                raise ValidationError("Некорректное действие с фотографией") from error
        if action == Actions.EDIT_ITEM and len(args) == 3:
            userId, itemId, data = args
            if not isinstance(data, dict):
                raise ValidationError("Характеристики вещи должны быть объектом")
            try:
                userId, itemId = int(userId), int(itemId)
            except (ValueError, TypeError) as error:
                raise ValidationError("Некорректный идентификатор") from error
            current = self.wardrobeController.getItem(userId, itemId)
            item = item_from_data(data, userId, current)
            return Response.ok(self.wardrobeController.updateItem(userId, itemId, item))
        raise ValidationError("Неизвестное действие загрузки")


def _validate_card_fields(data: dict) -> None:
    aliases = {
        "type": ("type",),
        "color": ("color",),
        "part": ("part",),
        "seasons": ("seasons",),
        "minTemperature": ("minTemperature", "min_temperature"),
        "maxTemperature": ("maxTemperature", "max_temperature"),
    }
    missing = [name for name, keys in aliases.items() if not any(key in data for key in keys)]
    if missing:
        raise ValidationError("Заполните поля карточки: " + ", ".join(missing))
    if not isinstance(data["seasons"], list) or not data["seasons"]:
        raise ValidationError("Укажите хотя бы один сезон")

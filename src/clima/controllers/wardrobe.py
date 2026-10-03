from clima.errors import AccessDeniedError, NotFoundError, ValidationError
from clima.integrations.photo_storage import PhotoStorage
from clima.models.entities import Item
from clima.repositories.items import ItemsRepository
import mimetypes


class WardrobeController:
    def __init__(self, itemsRepository: ItemsRepository, photoStorage: PhotoStorage):
        self.itemsRepository = itemsRepository
        self.photoStorage = photoStorage

    def getItems(self, userId: int) -> list[Item]:
        return self.itemsRepository.findByUser(userId)

    def getWardrobe(self, userId: int) -> list[Item]:
        return self.getItems(userId)

    def getItem(self, userId: int, itemId: int) -> Item:
        return self._ownedItem(userId, itemId)

    def getItemPhoto(self, userId: int, itemId: int) -> bytes:
        item = self._ownedItem(userId, itemId)
        return self.photoStorage.read(item.photo)

    def getItemPhotoContentType(self, userId: int, itemId: int) -> str:
        item = self._ownedItem(userId, itemId)
        return mimetypes.guess_type(item.photo)[0] or "application/octet-stream"

    def addItem(self, userId: int, photo: bytes) -> Item:
        return Item(userId=userId, photo=self.photoStorage.save(userId, photo))

    def confirmItem(self, userId: int, item: Item) -> Item:
        item.userId = userId
        item.validate()
        if item.id:
            current = self._ownedItem(userId, item.id)
            current.update(item)
            self.itemsRepository.update(current)
            return current
        if not self.photoStorage.belongsTo(userId, item.photo):
            raise ValidationError("Фото не загружено или не принадлежит пользователю")
        try:
            self.itemsRepository.add(item)
        except Exception:
            self.photoStorage.delete(item.photo)
            raise
        return item

    def updateItem(self, userId: int, itemId: int, data: Item) -> Item:
        current = self._ownedItem(userId, itemId)
        data.validate()
        current.update(data)
        self.itemsRepository.update(current)
        return current

    def updateItemPhoto(self, userId: int, itemId: int, photo: bytes) -> Item:
        item = self._ownedItem(userId, itemId)
        old_photo = item.photo
        new_photo = self.photoStorage.save(userId, photo)
        item.setPhoto(new_photo)
        try:
            self.itemsRepository.update(item)
        except Exception:
            self.photoStorage.delete(new_photo)
            raise
        if old_photo:
            self.photoStorage.delete(old_photo)
        return item

    def deleteItem(self, userId: int, itemId: int) -> None:
        item = self._ownedItem(userId, itemId)
        item.markDeleted()
        self.itemsRepository.update(item)

    def markInLaundry(self, userId: int, itemId: int, value: bool) -> None:
        item = self._ownedItem(userId, itemId)
        item.setInLaundry(value)
        self.itemsRepository.update(item)

    def _ownedItem(self, userId: int, itemId: int) -> Item:
        item = self.itemsRepository.findById(itemId)
        if item is None or item.deleted:
            raise NotFoundError("Вещь не найдена")
        if not item.belongsTo(userId):
            raise AccessDeniedError("Нет доступа к объекту")
        return item

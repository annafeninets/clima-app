from datetime import datetime, time

from clima.errors import NotFoundError, ValidationError
from clima.integrations.push import PushService
from clima.models.entities import Outfit, User
from clima.models.value_objects import Messages, PushSubscription
from clima.repositories.users import UsersRepository

WARDROBE_LABELS = {
    "top": "верх",
    "outerwear": "верхняя одежда",
    "bottom": "низ",
    "shoes": "обувь",
    "bag": "сумка",
    "hat": "головной убор",
    "accessories": "аксессуары",
}


def formatMissingText(missing: list[str]) -> str:
    if not missing:
        return "Добавьте вещи в гардероб"
    labels = ", ".join(WARDROBE_LABELS.get(category, category) for category in missing)
    return f"Не хватает: {labels}. Добавьте, чтобы получить образ"


class NotificationController:
    def __init__(self, usersRepository: UsersRepository, pushService: PushService):
        self.usersRepository = usersRepository
        self.pushService = pushService

    def setMorningNotification(self, userId: int, enabled: bool, time: time) -> None:
        user = self._user(userId)
        user.setNotification(enabled, time)
        self.usersRepository.update(user)

    def subscribePush(
        self,
        userId: int,
        subscription: PushSubscription,
        notificationTime: time | None = None,
        timeZone: str | None = None,
    ) -> None:
        user = self._user(userId)
        user.settings.pushSubscription = subscription
        if notificationTime is not None:
            user.setNotification(True, notificationTime)
        if timeZone is not None:
            user.settings.timeZone = timeZone
        self.usersRepository.update(user)

    def unsubscribePush(self, userId: int) -> None:
        user = self._user(userId)
        user.settings.pushSubscription = None
        self.usersRepository.update(user)

    def findDueUsers(self, now: datetime) -> list[User]:
        return self.usersRepository.findDueUsers(now)

    def findNotificationUsers(self) -> list[User]:
        return self.usersRepository.findNotificationUsers()

    def hasPushSubscription(self, userId: int) -> bool:
        user = self._user(userId)
        return user.settings.notificationsEnabled and user.settings.pushSubscription is not None

    def sendMorningOutfit(self, userId: int, outfit: Outfit) -> None:
        user = self._user(userId)
        if not user.settings.notificationsEnabled or user.settings.pushSubscription is None:
            return
        self.pushService.send(
            user.settings.pushSubscription,
            "Утренний аутфит",
            "Посмотрите образ на сегодня",
            "/outfits/today",
            "daily-outfit",
        )

    def sendWardrobeHint(self, userId: int, missing: list[str]) -> None:
        user = self._user(userId)
        if not user.settings.notificationsEnabled or user.settings.pushSubscription is None:
            return
        categories = ",".join(missing)
        body = (
            formatMissingText(missing)
            if missing
            else "Не удалось собрать образ. Проверьте, что вещи доступны и подходят погоде."
        )
        self.pushService.send(
            user.settings.pushSubscription,
            "Добавьте вещи в гардероб",
            body,
            f"/wardrobe?missing={categories}" if categories else "/wardrobe",
            "wardrobe-hint",
        )

    def sendHint(self, userId: int) -> None:
        user = self._user(userId)
        if user.settings.notificationsEnabled and user.settings.pushSubscription:
            self.pushService.send(
                user.settings.pushSubscription,
                "Утренний аутфит",
                "Добавьте город в настройках, чтобы получить образ на день.",
                "/settings",
                "daily-outfit",
            )

    def _user(self, userId: int) -> User:
        user = self.usersRepository.findById(userId)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        return user

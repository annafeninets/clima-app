from datetime import datetime, time

from clima.errors import NotFoundError, ValidationError
from clima.integrations.push import PushService
from clima.models.entities import Outfit, User
from clima.models.value_objects import Messages, PushSubscription
from clima.repositories.users import UsersRepository


class NotificationController:
    def __init__(self, usersRepository: UsersRepository, pushService: PushService):
        self.usersRepository = usersRepository
        self.pushService = pushService

    def setMorningNotification(self, userId: int, enabled: bool, time: time) -> None:
        user = self._user(userId)
        user.setNotification(enabled, time)
        self.usersRepository.update(user)

    def subscribePush(self, userId: int, subscription: PushSubscription) -> None:
        user = self._user(userId)
        user.settings.pushSubscription = subscription
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
        labels = ", ".join(item.type for item in outfit.items)
        body = f"Сегодня в {outfit.place}: {labels or 'откройте приложение, чтобы выбрать образ'}"
        self.pushService.send(user.settings.pushSubscription, "Утренний аутфит", body)

    def sendHint(self, userId: int) -> None:
        user = self._user(userId)
        if user.settings.notificationsEnabled and user.settings.pushSubscription:
            self.pushService.send(
                user.settings.pushSubscription, "Clima", "Добавьте вещи в гардероб, чтобы получать образы."
            )

    def _user(self, userId: int) -> User:
        user = self.usersRepository.findById(userId)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        return user

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from clima.controllers.notifications import NotificationController
from clima.controllers.profile import ProfileController
from clima.controllers.users import AuthController
from clima.errors import ValidationError
from clima.handlers.base import Handler
from clima.handlers.helpers import parse_time, preferences_from_data, push_subscription
from clima.models.enums import Actions, Theme
from clima.models.value_objects import Request, Response


class SettingsHandler(Handler):
    def __init__(
        self,
        authController: AuthController,
        profileController: ProfileController,
        notificationController: NotificationController,
    ):
        super().__init__(authController)
        self.profileController = profileController
        self.notificationController = notificationController

    def handle(self, request: Request) -> Response:
        if request.path.startswith("/auth/"):
            return self._auth(request)
        userId = self.authenticate(request)
        if request.path == "/profile" and request.method == "GET":
            return Response.ok(self.profileController.getProfile(userId))
        if request.path == "/profile" and request.method == "PUT":
            if "location" in request.body:
                location = request.body["location"]
                if not isinstance(location, str):
                    raise ValidationError("Место должно быть строкой")
                if not location.strip() or len(location.strip()) > 200:
                    raise ValidationError("Укажите корректное место")
            self.profileController.saveProfile(userId, preferences_from_data(request.body))
            if "location" in request.body:
                location = request.body["location"]
                self.profileController.setLocation(userId, location)
            return Response.ok(message="Анкета сохранена")
        if request.path == "/profile/location" and request.method == "GET":
            return Response.ok({"location": self.profileController.getLocation(userId)})
        if request.path == "/profile/location" and request.method == "PUT":
            location = request.body.get("location")
            if not isinstance(location, str):
                raise ValidationError("Место должно быть строкой")
            self.profileController.setLocation(userId, location)
            return Response.ok({"location": location.strip()}, "Место сохранено")
        if request.path == "/settings" and request.method == "GET":
            return Response.ok(self.profileController.getSettings(userId))
        if request.path == "/settings/theme" and request.method == "PUT":
            try:
                theme = Theme(request.body.get("theme", ""))
            except ValueError as error:
                raise ValidationError("Тема должна быть LIGHT или DARK") from error
            self.profileController.setTheme(userId, theme)
            return Response.ok(message="Тема применена")
        if request.path == "/settings/notifications" and request.method == "PUT":
            enabled = request.body.get("enabled")
            if not isinstance(enabled, bool):
                raise ValidationError("Поле enabled должно быть boolean")
            zone = None
            if request.body.get("timeZone") is not None:
                zone = str(request.body["timeZone"])
                try:
                    ZoneInfo(zone)
                except (ZoneInfoNotFoundError, ValueError) as error:
                    raise ValidationError("Некорректный часовой пояс") from error
            self.handleNotificationChange(
                enabled, parse_time(request.body.get("time", "07:00")), userId
            )
            if zone is not None:
                self.profileController.setTimeZone(userId, zone)
            settings = self.profileController.getSettings(userId)
            return Response.ok(settings, "Настройки уведомлений сохранены")
        if request.path == "/push/subscriptions" and request.method == "POST":
            self.notificationController.subscribePush(userId, push_subscription(request.body))
            return Response.ok(message="Push-подписка сохранена")
        if request.path == "/push/subscribe" and request.method == "POST":
            subscription = request.body.get("subscription")
            if not isinstance(subscription, dict):
                raise ValidationError("Некорректная push-подписка")
            parsedSubscription = push_subscription(subscription)
            notificationTime = None
            zone = None
            if "time" in request.body or "timezone" in request.body:
                if "time" not in request.body or "timezone" not in request.body:
                    raise ValidationError("Укажите время и часовой пояс")
                notificationTime = parse_time(request.body.get("time", "07:00"))
                zone = request.body.get("timezone")
                if not isinstance(zone, str):
                    raise ValidationError("Некорректный часовой пояс")
                try:
                    ZoneInfo(zone)
                except (ZoneInfoNotFoundError, ValueError) as error:
                    raise ValidationError("Некорректный часовой пояс") from error
            self.notificationController.subscribePush(
                userId, parsedSubscription, notificationTime, zone
            )
            return Response.ok(message="Push-подписка сохранена")
        if request.path == "/push/subscriptions" and request.method == "DELETE":
            self.notificationController.unsubscribePush(userId)
            return Response.ok(message="Push-подписка удалена")
        if request.path == "/account" and request.method == "DELETE":
            if request.query.get("confirm", "").lower() != "true":
                return Response(
                    True, "Подтвердите удаление аккаунта",
                    {"confirmationRequired": True}, 202,
                )
            self.authController.confirmDelete(userId)
            return Response.ok({"deleted": True}, "Аккаунт удалён")
        if request.path == "/auth/logout" and request.method == "POST":
            self.authController.endSession(userId)
            return Response.ok(message="Сессия завершена")
        raise ValidationError("Неизвестный раздел настроек")

    def _auth(self, request: Request) -> Response:
        if request.path == "/auth/logout" and request.method == "POST":
            userId = self.authenticate(request)
            self.authController.endSession(userId)
            return Response.ok(message="Сессия завершена")
        raise ValidationError("Неизвестная операция авторизации")

    def handleSettingsOpen(self, section: str, userId: int = 0) -> Response:
        available = {"preferences", "notifications", "theme", "account"}
        if section not in available:
            raise ValidationError("Неизвестный раздел настроек")
        if userId:
            if section == "preferences":
                return Response.ok(self.profileController.getProfile(userId))
            return Response.ok(self.profileController.getSettings(userId))
        return Response.ok({"section": section})

    def handleSettingsAction(
        self, action: str, userId: int = 0, data: dict | None = None
    ) -> Response:
        if action in {"LIGHT", "DARK", Actions.SET_THEME}:
            raw_theme = data.get("theme", "") if action == Actions.SET_THEME and data else action
            try:
                theme = Theme(raw_theme)
            except ValueError as error:
                raise ValidationError("Тема должна быть LIGHT или DARK") from error
            if userId:
                self.profileController.setTheme(userId, theme)
            return Response.ok({"theme": theme.value})
        if action in {"DELETE_ACCOUNT", Actions.DELETE_ACCOUNT}:
            return Response.ok({"confirmationRequired": True})
        if action == Actions.CONFIRM_DELETE and userId:
            self.authController.confirmDelete(userId)
            return Response.ok({"deleted": True})
        if action == Actions.SET_NOTIFICATION and userId and data:
            enabled = data.get("enabled")
            if not isinstance(enabled, bool):
                raise ValidationError("Поле enabled должно быть boolean")
            return self.handleNotificationChange(
                enabled, parse_time(data.get("time", "07:00")), userId
            )
        raise ValidationError("Неизвестное действие настроек")

    def handleNotificationChange(
        self, enabled: bool, time: time, userId: int = 0
    ) -> Response:
        if userId <= 0:
            raise ValidationError("Требуется авторизованный пользователь")
        self.notificationController.setMorningNotification(userId, enabled, time)
        return Response.ok(message="Настройки уведомлений сохранены")

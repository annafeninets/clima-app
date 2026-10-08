from datetime import datetime, time, timezone
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from clima.cache import Cache, MemoryCache
from clima.controllers.notifications import NotificationController
from clima.controllers.profile import ProfileController
from clima.controllers.users import AuthController
from clima.errors import ValidationError
from clima.handlers.base import Handler
from clima.handlers.helpers import parse_time, preferences_from_data, push_subscription
from clima.models.enums import Actions, Theme
from clima.models.value_objects import Request, Response
from clima.push_limits import (
    MAX_DAILY_PUSHES, localDate, pushCountKey, pushSentKey, secondsUntilLocalMidnight,
    wardrobeHintSentKey,
)

logger = logging.getLogger(__name__)


class SettingsHandler(Handler):
    def __init__(
        self,
        authController: AuthController,
        profileController: ProfileController,
        notificationController: NotificationController,
        cache: Cache | None = None,
    ):
        super().__init__(authController)
        self.profileController = profileController
        self.notificationController = notificationController
        self.cache = cache if cache is not None else MemoryCache()

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
        if (
            request.path == "/settings/notifications" and request.method == "PUT"
        ) or (
            request.path == "/push/settings" and request.method == "POST"
        ):
            return self._savePushSettings(userId, request.body)
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
            subscriptionSettings = None
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
                subscriptionSettings = self._savePushSettings(userId, {
                    "enabled": True,
                    "time": notificationTime.isoformat(),
                    "timeZone": zone,
                })
            self.notificationController.subscribePush(userId, parsedSubscription)
            return subscriptionSettings or Response.ok(message="Push-подписка сохранена")
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

    def _savePushSettings(self, userId: int, body: dict) -> Response:
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            raise ValidationError("Поле enabled должно быть boolean")
        notificationTime = parse_time(body.get("time", "07:00"))
        oldSettings = self.profileController.getSettings(userId)
        rawZone = body.get("timeZone", body.get("timezone", oldSettings.timeZone))
        if not isinstance(rawZone, str) or not rawZone.strip():
            raise ValidationError("Некорректный часовой пояс")
        zone = rawZone.strip()
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValidationError("Некорректный часовой пояс") from error

        timeChanged = oldSettings.notificationTime != notificationTime
        zoneChanged = oldSettings.timeZone != zone
        now = datetime.now(timezone.utc)
        oldDay = localDate(now, oldSettings.timeZone)
        newDay = localDate(now, zone)
        oldCountKey = pushCountKey(userId, oldDay)
        newCountKey = pushCountKey(userId, newDay)
        oldCount = int(self.cache.get(oldCountKey) or 0)
        newCount = int(self.cache.get(newCountKey) or 0)
        dailyCount = max(oldCount, newCount)
        if zoneChanged and oldDay != newDay and dailyCount:
            self.cache.set(
                newCountKey,
                str(dailyCount),
                secondsUntilLocalMidnight(now, zone),
            )

        localNow = now.astimezone(ZoneInfo(zone))
        requestedMinute = notificationTime.hour * 60 + notificationTime.minute
        currentMinute = localNow.hour * 60 + localNow.minute
        timeStillAhead = requestedMinute >= currentMinute
        changed = timeChanged or zoneChanged
        cacheAvailable = self.cache.ping() if changed and timeStillAhead else True
        reset = (
            changed and timeStillAhead and cacheAvailable
            and dailyCount < MAX_DAILY_PUSHES
        )
        limitReached = changed and dailyCount >= MAX_DAILY_PUSHES

        self.notificationController.setMorningNotification(
            userId, enabled, notificationTime, zone
        )
        if reset:
            oldKeys = (
                pushSentKey(userId, oldDay),
                wardrobeHintSentKey(userId, oldDay),
                f"scheduler:morning:{userId}:{oldDay.isoformat()}",
            )
            newKeys = (
                pushSentKey(userId, newDay),
                wardrobeHintSentKey(userId, newDay),
                f"scheduler:morning:{userId}:{newDay.isoformat()}",
            )
            self.cache.delete(*set(oldKeys + newKeys))
            resetReasons = []
            if timeChanged:
                resetReasons.append("time_changed")
            if zoneChanged:
                resetReasons.append("timezone_changed")
            logger.info(
                "[push] userId=%s flag reset reason=%s old=%s new=%s old_tz=%s new_tz=%s",
                userId,
                "_and_".join(resetReasons),
                oldSettings.notificationTime.strftime("%H:%M"),
                notificationTime.strftime("%H:%M"),
                oldSettings.timeZone,
                zone,
            )
        elif limitReached:
            logger.info(
                "[push] userId=%s notification settings changed; daily limit reached (%s)",
                userId,
                MAX_DAILY_PUSHES,
            )
        elif changed and timeStillAhead and not cacheAvailable:
            logger.error(
                "[push] userId=%s could not reset daily flag because the cache is unavailable",
                userId,
            )
        return Response.ok({
            "ok": True,
            "reset": reset,
            "limit_reached": limitReached,
        }, "Настройки уведомлений сохранены")

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

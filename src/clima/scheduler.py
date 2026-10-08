"""Daily local-time notification scheduler."""

from datetime import date, datetime
import logging
from threading import Event, RLock, Thread
from zoneinfo import ZoneInfo

from clima.cache import Cache, MemoryCache
from clima.controllers.notifications import NotificationController
from clima.controllers.outfits import OutfitController
from clima.errors import AppError, NotEnoughItemsError
from clima.push_limits import (
    MAX_DAILY_PUSHES,
    pushCountKey,
    pushSentKey,
    secondsUntilLocalMidnight,
    wardrobeHintSentKey,
)

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        scheduleHandler,
        outfitController: OutfitController,
        notificationController: NotificationController,
        cache: Cache | None = None,
    ):
        self.cache: Cache = cache if cache is not None else MemoryCache()
        self.scheduleHandler = scheduleHandler
        self.outfitController = outfitController
        self.notificationController = notificationController
        self._stop_event = Event()
        self._trigger_lock = RLock()
        self._thread: Thread | None = None

    def start(self, intervalSeconds: int = 20) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run, args=(intervalSeconds,), name="clima-morning-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def triggerMorningBroadcast(self) -> None:
        with self._trigger_lock:
            now = datetime.now().astimezone()
            for user in self.notificationController.findDueUsers(now):
                local_date = now.astimezone(ZoneInfo(user.settings.timeZone)).date()
                if not self.notificationController.hasPushSubscription(user.id):
                    continue
                if self._isDelivered(user.id, local_date):
                    continue
                if not self._canSend(user.id, local_date):
                    logger.info(
                        "[push] userId=%s skipped daily limit date=%s",
                        user.id,
                        local_date,
                    )
                    continue
                if not user.location.strip():
                    try:
                        self.notificationController.sendHint(user.id)
                    except AppError:
                        logger.exception("Не удалось отправить подсказку пользователю %s", user.id)
                    else:
                        self._markDelivered(user, local_date, now, "daily-outfit")
                    continue
                try:
                    outfit = self.outfitController.getTodayOutfit(user.id)
                    self.notificationController.sendMorningOutfit(user.id, outfit)
                    self._markDelivered(user, local_date, now, "daily-outfit")
                except NotEnoughItemsError as error:
                    try:
                        status = self.outfitController.getWardrobeStatus(user.id)
                        if self._isWardrobeHintDelivered(user.id, local_date):
                            continue
                        if not self._canSend(user.id, local_date):
                            logger.info(
                                "[push] userId=%s skipped wardrobe-hint daily limit date=%s",
                                user.id,
                                local_date,
                            )
                            continue
                        missing = status["missing"]
                        self.notificationController.sendWardrobeHint(user.id, missing)
                    except AppError:
                        logger.exception("Не удалось отправить подсказку пользователю %s", user.id)
                    except Exception:
                        logger.exception("Ошибка подготовки подсказки пользователю %s", user.id)
                    else:
                        self._markWardrobeHintDelivered(user, local_date, now)
                        logger.info(
                            "Отправлена подсказка о гардеробе пользователю %s; missing=%s",
                            user.id,
                            error.missing or missing,
                        )
                except AppError:
                    logger.exception("Не удалось отправить утренний аутфит пользователю %s", user.id)

    @staticmethod
    def _deliveredKey(userId: int, day: date) -> str:
        return pushSentKey(userId, day)

    def _isDelivered(self, userId: int, day: date) -> bool:
        return (
            self.cache.get(self._deliveredKey(userId, day)) is not None
            or self.cache.get(f"scheduler:morning:{userId}:{day.isoformat()}") is not None
        )

    def _canSend(self, userId: int, day: date) -> bool:
        rawCount = self.cache.get(pushCountKey(userId, day))
        if rawCount is None and not self.cache.ping():
            logger.error(
                "[push] userId=%s skipped because the daily limit cache is unavailable",
                userId,
            )
            return False
        try:
            count = int(rawCount or 0)
        except ValueError:
            logger.error(
                "[push] userId=%s has an invalid daily push counter",
                userId,
            )
            return False
        return count < MAX_DAILY_PUSHES

    def _markDelivered(self, user, day: date, now: datetime, pushType: str) -> None:
        self._markPushSent(user, day, now)
        logger.info(
            "[push] userId=%s type=%s time=%s tz=%s",
            user.id,
            pushType,
            user.settings.notificationTime.strftime("%H:%M"),
            user.settings.timeZone,
        )

    def _isWardrobeHintDelivered(self, userId: int, day: date) -> bool:
        return self.cache.get(wardrobeHintSentKey(userId, day)) is not None

    def _markWardrobeHintDelivered(self, user, day: date, now: datetime) -> None:
        self.cache.set(
            wardrobeHintSentKey(user.id, day),
            "1",
            secondsUntilLocalMidnight(now, user.settings.timeZone),
        )
        self._markPushCount(user.id, day, now, user.settings.timeZone)
        logger.info(
            "[push] userId=%s type=wardrobe-hint time=%s tz=%s",
            user.id,
            user.settings.notificationTime.strftime("%H:%M"),
            user.settings.timeZone,
        )

    def _markPushSent(self, user, day: date, now: datetime) -> None:
        self.cache.set(
            self._deliveredKey(user.id, day),
            "1",
            secondsUntilLocalMidnight(now, user.settings.timeZone),
        )
        self._markPushCount(user.id, day, now, user.settings.timeZone)

    def _markPushCount(self, userId: int, day: date, now: datetime, timeZone: str) -> None:
        count = self.cache.increment(
            pushCountKey(userId, day),
            secondsUntilLocalMidnight(now, timeZone),
        )
        if count is None:
            logger.error(
                "[push] userId=%s sent but daily rate-limit counter unavailable",
                userId,
            )

    def _run(self, intervalSeconds: int) -> None:
        while not self._stop_event.is_set():
            self.triggerMorningBroadcast()
            self._stop_event.wait(intervalSeconds)

"""Daily local-time notification scheduler."""

from datetime import date, datetime, time, timedelta, timezone
import logging
from threading import Event, RLock, Thread
from zoneinfo import ZoneInfo

from clima.cache import Cache, MemoryCache
from clima.controllers.notifications import NotificationController
from clima.controllers.outfits import OutfitController
from clima.errors import AppError, NotEnoughItemsError

logger = logging.getLogger(__name__)

# Отметка «уже отправили» живёт чуть дольше суток: перекрывает любую смену локальной даты.
DELIVERED_TTL_SECONDS = 36 * 3600


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
        # Локальная копия страхует от дублей, если Redis недоступен; общий кеш — от дублей после
        # перезапуска и при нескольких экземплярах backend.
        self._delivered: dict[int, date] = {}
        self._wardrobe_hint_delivered: dict[int, date] = {}
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
                if not user.location.strip():
                    try:
                        self.notificationController.sendHint(user.id)
                    except AppError:
                        logger.exception("Не удалось отправить подсказку пользователю %s", user.id)
                    else:
                        self._markDelivered(user.id, local_date)
                    continue
                try:
                    outfit = self.outfitController.getTodayOutfit(user.id)
                    self.notificationController.sendMorningOutfit(user.id, outfit)
                    self._markDelivered(user.id, local_date)
                except NotEnoughItemsError as error:
                    try:
                        status = self.outfitController.getWardrobeStatus(user.id)
                        if self._isWardrobeHintDelivered(user.id, local_date):
                            continue
                        missing = status["missing"]
                        self.notificationController.sendWardrobeHint(user.id, missing)
                    except AppError:
                        logger.exception("Не удалось отправить подсказку пользователю %s", user.id)
                    except Exception:
                        logger.exception("Ошибка подготовки подсказки пользователю %s", user.id)
                    else:
                        self._markWardrobeHintDelivered(
                            user.id, local_date, user.settings.timeZone, now
                        )
                        logger.info(
                            "Отправлена подсказка о гардеробе пользователю %s; missing=%s",
                            user.id,
                            error.missing or missing,
                        )
                except AppError:
                    logger.exception("Не удалось отправить утренний аутфит пользователю %s", user.id)

    @staticmethod
    def _deliveredKey(userId: int, day: date) -> str:
        return f"scheduler:morning:{userId}:{day.isoformat()}"

    def _isDelivered(self, userId: int, day: date) -> bool:
        if self._delivered.get(userId) == day:
            return True
        return self.cache.get(self._deliveredKey(userId, day)) is not None

    def _markDelivered(self, userId: int, day: date) -> None:
        self._delivered[userId] = day
        self.cache.set(self._deliveredKey(userId, day), "1", DELIVERED_TTL_SECONDS)

    @staticmethod
    def _wardrobeHintKey(userId: int, day: date) -> str:
        return f"wardrobe_hint_sent:{userId}:{day.isoformat()}"

    def _isWardrobeHintDelivered(self, userId: int, day: date) -> bool:
        if self._wardrobe_hint_delivered.get(userId) == day:
            return True
        return self.cache.get(self._wardrobeHintKey(userId, day)) is not None

    def _markWardrobeHintDelivered(
        self, userId: int, day: date, timeZone: str, now: datetime
    ) -> None:
        self._wardrobe_hint_delivered[userId] = day
        zone = ZoneInfo(timeZone)
        local_now = now.astimezone(zone)
        next_midnight = datetime.combine(day + timedelta(days=1), time.min, zone)
        ttl = max(
            1,
            (
                next_midnight.astimezone(timezone.utc)
                - local_now.astimezone(timezone.utc)
            ).total_seconds(),
        )
        self.cache.set(self._wardrobeHintKey(userId, day), "1", ttl)

    def _run(self, intervalSeconds: int) -> None:
        while not self._stop_event.is_set():
            self.triggerMorningBroadcast()
            self._stop_event.wait(intervalSeconds)

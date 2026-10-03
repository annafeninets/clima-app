"""Daily local-time notification scheduler."""

from datetime import date, datetime
import logging
from threading import Event, RLock, Thread
from zoneinfo import ZoneInfo

from clima.controllers.notifications import NotificationController
from clima.controllers.outfits import OutfitController
from clima.errors import AppError, NotEnoughItemsError

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        scheduleHandler,
        outfitController: OutfitController,
        notificationController: NotificationController,
    ):
        self.scheduleHandler = scheduleHandler
        self.outfitController = outfitController
        self.notificationController = notificationController
        self._stop_event = Event()
        self._trigger_lock = RLock()
        self._delivered: dict[int, date] = {}
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
                if self._delivered.get(user.id) == local_date:
                    continue
                if not user.location.strip():
                    try:
                        self.notificationController.sendHint(user.id)
                    except AppError:
                        logger.exception("Не удалось отправить подсказку пользователю %s", user.id)
                    else:
                        self._delivered[user.id] = local_date
                    continue
                try:
                    outfit = self.outfitController.getTodayOutfit(user.id)
                    self.notificationController.sendMorningOutfit(user.id, outfit)
                    self._delivered[user.id] = local_date
                except NotEnoughItemsError:
                    try:
                        self.notificationController.sendHint(user.id)
                    except AppError:
                        logger.exception("Не удалось отправить подсказку пользователю %s", user.id)
                    else:
                        self._delivered[user.id] = local_date
                except AppError:
                    logger.exception("Не удалось отправить утренний аутфит пользователю %s", user.id)

    def _run(self, intervalSeconds: int) -> None:
        while not self._stop_event.is_set():
            self.triggerMorningBroadcast()
            self._stop_event.wait(intervalSeconds)

import hmac
import os

from clima.cache import Cache
from clima.controllers.notifications import NotificationController
from clima.controllers.outfits import OutfitController
from clima.controllers.users import AuthController
from clima.errors import AccessDeniedError, ValidationError
from clima.handlers.base import Handler
from clima.models.value_objects import Request, Response
from clima.scheduler import Scheduler


class ScheduleHandler(Handler):
    def __init__(
        self, authController: AuthController, outfitController: OutfitController,
        notificationController: NotificationController, cache: Cache | None = None,
    ):
        super().__init__(authController)
        self.outfitController = outfitController
        self.notificationController = notificationController
        self._scheduler = Scheduler(
            self, outfitController, notificationController, cache
        )

    def handle(self, request: Request) -> Response:
        expected = os.environ.get("CLIMA_SCHEDULER_TOKEN")
        provided = request.headers.get("x-scheduler-token", "")
        if not expected or not hmac.compare_digest(provided, expected):
            raise AccessDeniedError("Нет доступа к планировщику")
        self.handleSchedule(request.body.get("mode", "morning"), [])
        return Response.ok(message="Рассылка запущена")

    def handleSchedule(self, mode: str, args: list) -> None:
        if mode != "morning":
            raise ValidationError("Неизвестный режим планировщика")
        self._scheduler.triggerMorningBroadcast()

    def startBackground(self) -> None:
        self._scheduler.start()

    def stopBackground(self) -> None:
        self._scheduler.stop()

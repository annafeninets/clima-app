"""HTTP API routing and request/response serialization."""

from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from enum import Enum
import json
import logging
import re

from clima.errors import AppError, NotEnoughItemsError, NotFoundError
from clima.handlers.callback import CallbackHandler
from clima.handlers.command import CommandHandler
from clima.handlers.schedule import ScheduleHandler
from clima.handlers.settings import SettingsHandler
from clima.handlers.upload import UploadHandler
from clima.models.entities import Item
from clima.models.entities.settings import Settings
from clima.models.value_objects import Request, Response

logger = logging.getLogger(__name__)


class ClimaApi:
    _routes = (
        (r"/auth/form", "GET", "commandHandler"),
        (r"/auth/login", "POST", "commandHandler"),
        (r"/auth/register", "POST", "commandHandler"),
        (r"/auth/logout", "POST", "settingsHandler"),
        (r"/profile", "GET|PUT", "settingsHandler"),
        (r"/profile/location", "GET|PUT", "settingsHandler"),
        (r"/settings", "GET", "settingsHandler"),
        (r"/settings/theme", "PUT", "settingsHandler"),
        (r"/settings/notifications", "PUT", "settingsHandler"),
        (r"/push/subscribe", "POST", "settingsHandler"),
        (r"/push/subscriptions", "POST", "settingsHandler"),
        (r"/push/subscriptions", "DELETE", "settingsHandler"),
        (r"/account", "DELETE", "settingsHandler"),
        (r"/wardrobe", "GET", "callbackHandler"),
        (r"/wardrobe/status", "GET", "callbackHandler"),
        (r"/wardrobe/items", "POST", "uploadHandler"),
        (r"/wardrobe/items/draft", "PUT", "uploadHandler"),
        (r"/wardrobe/items/\d+/photo", "GET|PUT", "callbackHandler"),
        (r"/wardrobe/items/\d+/laundry", "PUT", "callbackHandler"),
        (r"/wardrobe/items/\d+", "GET|PUT|DELETE", "callbackHandler"),
        (r"/outfits/plan", "GET", "commandHandler"),
        (r"/outfits/today", "GET", "commandHandler"),
        (r"/outfits/history", "GET", "commandHandler"),
        (r"/outfits/rate", "GET", "commandHandler"),
        (r"/outfits/\d+/rating", "PUT", "callbackHandler"),
        (r"/outfits/\d+/select", "POST", "commandHandler"),
        (r"/outfits/\d+", "GET", "commandHandler"),
        (r"/favorites", "GET|POST", "callbackHandler"),
        (r"/favorites/compose", "POST", "callbackHandler"),
        (r"/favorites/\d+/items/\d+", "PUT", "callbackHandler"),
        (r"/favorites/\d+", "GET|DELETE", "callbackHandler"),
        (r"/internal/scheduler/morning", "POST", "scheduleHandler"),
    )

    def __init__(
        self,
        commandHandler: CommandHandler,
        uploadHandler: UploadHandler,
        callbackHandler: CallbackHandler,
        scheduleHandler: ScheduleHandler,
        settingsHandler: SettingsHandler,
    ):
        self.commandHandler = commandHandler
        self.uploadHandler = uploadHandler
        self.callbackHandler = callbackHandler
        self.scheduleHandler = scheduleHandler
        self.settingsHandler = settingsHandler

    def dispatch(self, request: Request) -> Response:
        try:
            request.action = f"{request.method} {request.path}"
            for pattern, methods, handler_name in self._routes:
                if request.method in methods.split("|") and re.fullmatch(pattern, request.path):
                    return getattr(self, handler_name).handle(request)
            raise NotFoundError("Маршрут не найден")
        except AppError as error:
            if isinstance(error, NotEnoughItemsError) and error.missing is not None:
                return Response(
                    False,
                    error.message,
                    {
                        "code": error.code,
                        "error": error.code,
                        "missing": error.missing,
                        "have": error.have,
                    },
                    error.status_code,
                )
            return Response.error(error.message, error.status_code, error.code)
        except Exception:
            logger.exception("Unhandled backend error for %s %s", request.method, request.path)
            return Response.error("Внутренняя ошибка сервера", 500, "internal_error")


def response_bytes(response: Response) -> tuple[bytes, str]:
    if isinstance(response.data, bytes):
        return response.data, response.contentType
    data = {
        "success": response.success,
        "message": response.message,
        "data": to_jsonable(response.data),
    }
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), response.contentType


def to_jsonable(value):
    if isinstance(value, Settings):
        return {
            "theme": to_jsonable(value.theme),
            "notificationsEnabled": value.notificationsEnabled,
            "notificationTime": to_jsonable(value.notificationTime),
            "timeZone": value.timeZone,
            "pushSubscribed": value.pushSubscription is not None,
        }
    if isinstance(value, Item):
        result = {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
        result["photo"] = (
            f"/wardrobe/items/{value.id}/photo" if value.id and value.photo else value.photo or None
        )
        return result
    if is_dataclass(value):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value

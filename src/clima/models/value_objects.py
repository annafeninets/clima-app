from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from clima.errors import ValidationError
from clima.models.enums import Season


class Messages:
    INVALID_CREDENTIALS = "Неверный логин или пароль"
    PASSWORD_MISMATCH = "Пароли не совпадают"
    ACCOUNT_EXISTS = "Аккаунт с таким email или телефоном уже существует"
    SESSION_EXPIRED = "Сессия истекла"
    NOT_FOUND = "Объект не найден"
    ACCESS_DENIED = "Нет доступа к объекту"
    ALREADY_FAVORITE = "Аутфит уже добавлен в избранное"
    NOT_ENOUGH_ITEMS = "Недостаточно чистых вещей для подбора"
    CHANGE_FILTERS = "Измените фильтры или пополните гардероб"
    BAD_COMBINATION = "Эти вещи не сочетаются"
    FILL_WARDROBE = "Пополните гардероб, чтобы составить аутфит"


@dataclass(slots=True)
class Request:
    action: str
    args: list[Any] = field(default_factory=list)
    token: str = ""
    userId: int = 0
    method: str = ""
    path: str = ""
    query: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Response:
    success: bool
    message: str = ""
    data: Any = None
    status: int = 200
    contentType: str = "application/json; charset=utf-8"

    @staticmethod
    def ok(data: Any = None, message: str = "") -> "Response":
        return Response(True, message, data, 200)

    @staticmethod
    def error(message: str, status: int = 400, code: str = "application_error") -> "Response":
        return Response(False, message, {"code": code}, status)


@dataclass(slots=True)
class Session:
    token: str
    userId: int
    expiresAt: datetime

    def isExpired(self) -> bool:
        expires = self.expiresAt
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= datetime.now(timezone.utc)


@dataclass(slots=True)
class WeatherData:
    place: str
    date: date
    temperature: int
    conditions: str
    feelsLike: int | None = None
    windSpeed: float = 0.0
    humidity: int = 0
    precipitation: float = 0.0
    uvIndex: float = 0.0
    latitude: float | None = None
    longitude: float | None = None
    source: str = "forecast"


@dataclass(slots=True)
class CheckResult:
    compatible: bool
    reason: str


@dataclass(slots=True)
class OutfitFilter:
    date: date
    place: str
    occasion: str = ""
    temperature: int | None = None
    season: Season | None = None
    latitude: float | None = None
    longitude: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.temperature, bool):
            raise ValidationError("Температура должна быть целым числом")
        if self.temperature is not None and not isinstance(self.temperature, int):
            raise ValidationError("Температура должна быть целым числом")
        if self.season is not None and not isinstance(self.season, Season):
            raise ValidationError("Некорректный сезон")
        if not self.place.strip():
            raise ValidationError("Укажите место")
        if not self.occasion:
            self.occasion = "everyday"


@dataclass(slots=True)
class PushSubscription:
    endpoint: str
    p256dh: str
    auth: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.endpoint, str)
            or not isinstance(self.p256dh, str)
            or not isinstance(self.auth, str)
            or len(self.endpoint) > 2048
            or len(self.p256dh) > 256
            or len(self.auth) > 256
            or not self.endpoint.startswith("https://")
            or not self.p256dh
            or not self.auth
        ):
            raise ValidationError("Некорректная push-подписка")

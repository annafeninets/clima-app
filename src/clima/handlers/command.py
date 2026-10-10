from clima.controllers.outfits import OutfitController
from clima.controllers.profile import ProfileController
from clima.controllers.users import AuthController
from clima.errors import ValidationError
from clima.handlers.base import Handler
from clima.handlers.helpers import client_ip, outfit_filter, preferences_from_data
from clima.integrations.weather import WeatherService
from clima.models.value_objects import Request, Response


class CommandHandler(Handler):
    def __init__(
        self, authController: AuthController, profileController: ProfileController,
        outfitController: OutfitController, weatherService: WeatherService,
    ):
        super().__init__(authController)
        self.profileController = profileController
        self.outfitController = outfitController
        self.weatherService = weatherService

    def handle(self, request: Request) -> Response:
        if request.path == "/auth/form" and request.method == "GET":
            return Response.ok({"fields": ["login", "password"]})
        if request.path in ("/auth/login", "/auth/register") and request.method == "POST":
            body = request.body
            login = _string(body, "login")
            password = _string(body, "password")
            session = (
                self.authController.login(login, password)
                if request.path == "/auth/login"
                else self.authController.register(login, password, _string(body, "confirm"))
            )
            return Response.ok(session, "Добро пожаловать")
        userId = self.authenticate(request)
        if request.path == "/places/context" and request.method == "GET":
            return Response.ok(self.weatherService.placeContext(client_ip(request.headers)))
        if request.path == "/places/search" and request.method == "GET":
            query = request.query.get("q", "")
            country = request.query.get("country", "").strip().upper() or None
            seed = request.query.get("seed", "").strip() or None
            try:
                limit = int(request.query.get("limit", "10"))
            except ValueError as error:
                raise ValidationError("Параметр limit должен быть числом") from error
            places = self.weatherService.suggestPlaces(
                query, country, seed, client_ip(request.headers), limit,
            )
            return Response.ok(places)
        if request.path == "/outfits/plan" and request.method == "GET":
            return Response.ok(self.outfitController.planOutfit(
                userId, outfit_filter(request.query, self.profileController.getLocation(userId))
            ))
        if request.path == "/outfits/today" and request.method == "GET":
            return Response.ok(self.outfitController.getTodayOutfits(
                userId, request.query.get("location")
            ))
        if request.path == "/outfits/history" and request.method == "GET":
            return Response.ok(self.outfitController.getOutfitHistory(userId))
        if request.path == "/outfits/rate" and request.method == "GET":
            return Response.ok(self.outfitController.getOutfitsToRate(userId))
        if request.path.startswith("/outfits/"):
            outfitId = _path_id(request.path, "/outfits/")
            if request.method == "GET":
                return Response.ok(self.outfitController.getOutfit(userId, outfitId))
            if request.method == "POST" and request.path.endswith("/select"):
                return Response.ok(self.outfitController.selectOutfit(userId, outfitId))
        raise ValidationError("Неизвестная команда")

    def handleCommand(self, command: str, args: list) -> Response:
        if command == "/start":
            self.authController.startAuth()
            return Response.ok({"message": "Добро пожаловать в Clima"})
        if command == "/login" and len(args) >= 2:
            return Response.ok(self.authController.login(str(args[0]), str(args[1])))
        if command == "/register" and len(args) >= 3:
            return Response.ok(self.authController.register(
                str(args[0]), str(args[1]), str(args[2])
            ))
        if command == "/profile" and args:
            return Response.ok(self.profileController.getProfile(int(args[0])))
        if command == "/profile/save" and len(args) >= 2:
            userId, data = int(args[0]), args[1]
            if not isinstance(data, dict):
                raise ValidationError("Анкета должна быть объектом")
            self.profileController.saveProfile(userId, preferences_from_data(data))
            return Response.ok(message="Анкета сохранена")
        if command == "/history" and args:
            return Response.ok(self.outfitController.getOutfitHistory(int(args[0])))
        raise ValidationError("Неизвестная команда")


def _string(body: dict, key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Поле {key} обязательно")
    return value


def _path_id(path: str, prefix: str) -> int:
    try:
        return int(path.removeprefix(prefix).split("/", 1)[0])
    except ValueError as error:
        raise ValidationError("Некорректный идентификатор") from error

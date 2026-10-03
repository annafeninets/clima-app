"""Dependency wiring for the backend application."""

from pathlib import Path

from clima.api import ClimaApi
from clima.database.database import Database
from clima.controllers.feedback import FeedbackController
from clima.controllers.notifications import NotificationController
from clima.controllers.outfits import CompatibilityRule, OutfitController
from clima.controllers.profile import ProfileController
from clima.controllers.users import AuthController
from clima.controllers.wardrobe import WardrobeController
from clima.handlers.callback import CallbackHandler
from clima.handlers.command import CommandHandler
from clima.handlers.schedule import ScheduleHandler
from clima.handlers.settings import SettingsHandler
from clima.handlers.upload import UploadHandler
from clima.integrations.photo_storage import PhotoStorage
from clima.integrations.push import PushService
from clima.integrations.weather import WeatherService
from clima.repositories.favorites import FavoritesRepository
from clima.repositories.items import ItemsRepository
from clima.repositories.outfits import OutfitsRepository
from clima.repositories.users import UsersRepository


class Application:
    def __init__(
        self, databasePath: str | Path = "clima.sqlite3",
        photoRoot: str | Path = "uploads", weatherService: WeatherService | None = None,
        pushService: PushService | None = None,
    ):
        self.database = Database.getInstance(databasePath)
        self.photoStorage = PhotoStorage(photoRoot)
        self.usersRepository = UsersRepository(self.database)
        self.itemsRepository = ItemsRepository(self.database)
        self.outfitsRepository = OutfitsRepository(self.database, self.itemsRepository)
        self.favoritesRepository = FavoritesRepository(self.database)
        self.authController = AuthController(self.usersRepository, self.photoStorage)
        self.profileController = ProfileController(self.usersRepository)
        self.wardrobeController = WardrobeController(self.itemsRepository, self.photoStorage)
        self.compatibilityRule = CompatibilityRule()
        self.weatherService = weatherService or WeatherService()
        self.pushService = pushService or PushService()
        self.outfitController = OutfitController(
            self.itemsRepository, self.outfitsRepository, self.compatibilityRule,
            self.weatherService, self.usersRepository,
        )
        self.feedbackController = FeedbackController(
            self.favoritesRepository, self.outfitsRepository, self.itemsRepository,
            self.compatibilityRule,
        )
        self.notificationController = NotificationController(
            self.usersRepository, self.pushService
        )
        commandHandler = CommandHandler(
            self.authController, self.profileController, self.outfitController
        )
        uploadHandler = UploadHandler(self.authController, self.wardrobeController)
        callbackHandler = CallbackHandler(
            self.authController, self.outfitController, self.feedbackController,
            self.wardrobeController,
        )
        scheduleHandler = ScheduleHandler(
            self.authController, self.outfitController,
            self.notificationController,
        )
        settingsHandler = SettingsHandler(
            self.authController, self.profileController, self.notificationController
        )
        self.api = ClimaApi(
            commandHandler, uploadHandler, callbackHandler, scheduleHandler, settingsHandler
        )

    def close(self) -> None:
        Database.resetInstance()

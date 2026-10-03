from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from clima.errors import NotFoundError, ValidationError
from clima.models.entities import Preferences, Settings
from clima.models.enums import Theme
from clima.repositories.users import UsersRepository


class ProfileController:
    def __init__(self, usersRepository: UsersRepository):
        self.usersRepository = usersRepository

    def getProfile(self, userId: int) -> Preferences:
        return self._user(userId).preferences

    def saveProfile(self, userId: int, data: Preferences) -> None:
        user = self._user(userId)
        user.updatePreferences(data)
        self.usersRepository.update(user)

    def getLocation(self, userId: int) -> str:
        return self._user(userId).location

    def setLocation(self, userId: int, location: str) -> None:
        location = location.strip()
        if (
            len(location) < 2 or len(location) > 200
            or not any(character.isalpha() for character in location)
            or any(
                not character.isalpha() and not character.isspace()
                and character not in ".'’-"
                for character in location
            )
        ):
            raise ValidationError("Укажите корректное место")
        user = self._user(userId)
        user.location = location
        self.usersRepository.update(user)

    def setTimeZone(self, userId: int, timeZone: str) -> None:
        if not isinstance(timeZone, str) or not timeZone.strip():
            raise ValidationError("Некорректный часовой пояс")
        timeZone = timeZone.strip()
        try:
            ZoneInfo(timeZone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValidationError("Некорректный часовой пояс") from error
        user = self._user(userId)
        user.settings.timeZone = timeZone
        self.usersRepository.update(user)

    def getSettings(self, userId: int) -> Settings:
        return self._user(userId).settings

    def setTheme(self, userId: int, theme: Theme) -> None:
        try:
            theme = Theme(theme)
        except ValueError as error:
            raise ValidationError("Тема должна быть LIGHT или DARK") from error
        user = self._user(userId)
        user.setTheme(theme)
        self.usersRepository.update(user)

    def _user(self, userId: int):
        user = self.usersRepository.findById(userId)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        return user

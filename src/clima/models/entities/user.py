from dataclasses import dataclass, field
import hashlib
import hmac
import secrets

from clima.models.entities.base import Entity
from clima.models.entities.preferences import Preferences
from clima.models.entities.settings import Settings
from clima.models.enums import Theme


@dataclass(slots=True)
class User(Entity):
    email: str | None = None
    phone: str | None = None
    passwordHash: str = ""
    location: str = ""
    preferences: Preferences = field(default_factory=Preferences)
    settings: Settings = field(default_factory=Settings)

    def checkPassword(self, password: str) -> bool:
        try:
            algorithm, iterations, salt, digest = self.passwordHash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
            ).hex()
            return hmac.compare_digest(candidate, digest)
        except (ValueError, TypeError):
            return False

    def setPassword(self, password: str) -> None:
        salt = secrets.token_bytes(16)
        iterations = 310_000
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations).hex()
        self.passwordHash = f"pbkdf2_sha256${iterations}${salt.hex()}${digest}"

    def updatePreferences(self, data: Preferences) -> None:
        self.preferences = data

    def setTheme(self, theme: Theme) -> None:
        self.settings.theme = theme

    def setNotification(self, enabled: bool, time) -> None:
        self.settings.notificationsEnabled = enabled
        self.settings.notificationTime = time

from dataclasses import dataclass
from datetime import time

from clima.models.enums import Theme
from clima.models.value_objects import PushSubscription


@dataclass(slots=True)
class Settings:
    theme: Theme = Theme.LIGHT
    notificationsEnabled: bool = False
    notificationTime: time = time(7, 0)
    timeZone: str = "UTC"
    pushSubscription: PushSubscription | None = None

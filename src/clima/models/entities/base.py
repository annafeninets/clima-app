from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class Entity:
    id: int = 0
    createdAt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def getId(self) -> int:
        return self.id


@dataclass(slots=True)
class OwnedEntity(Entity):
    userId: int = 0

    def belongsTo(self, userId: int) -> bool:
        return self.userId == userId

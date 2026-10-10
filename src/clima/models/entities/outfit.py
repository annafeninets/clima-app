from dataclasses import dataclass, field
from datetime import date

from clima.errors import ValidationError
from clima.models.entities.base import OwnedEntity
from clima.models.entities.item import Item


@dataclass(slots=True)
class Outfit(OwnedEntity):
    date: date = field(default_factory=date.today)
    place: str = ""
    occasion: str = ""
    items: list[Item] = field(default_factory=list)
    selected: bool = False
    rating: int = 0
    debug: dict | None = None

    def setSelected(self, value: bool) -> None:
        self.selected = value

    def setRating(self, score: int) -> None:
        if not 1 <= score <= 5:
            raise ValidationError("Оценка должна быть от 1 до 5")
        self.rating = score

    def replaceItem(self, itemId: int, newItem: Item) -> None:
        for index, item in enumerate(self.items):
            if item.id == itemId:
                self.items[index] = newItem
                return
        raise ValidationError("Вещь не входит в аутфит")

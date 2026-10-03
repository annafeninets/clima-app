from dataclasses import dataclass, field

from clima.errors import ValidationError
from clima.models.entities.base import OwnedEntity
from clima.models.enums import ItemPart, Season


@dataclass(slots=True)
class Item(OwnedEntity):
    photo: str = ""
    type: str = ""
    color: str = ""
    seasons: list[Season] = field(default_factory=list)
    minTemperature: int = -100
    maxTemperature: int = 100
    part: ItemPart = ItemPart.TOP
    dressCode: str = "casual"
    style: str = ""
    silhouette: str = ""
    material: str = ""
    inLaundry: bool = False
    deleted: bool = False

    def setPhoto(self, path: str) -> None:
        self.photo = path

    def update(self, data: "Item") -> None:
        for name in (
            "type", "color", "seasons", "minTemperature", "maxTemperature",
            "part", "dressCode", "style", "silhouette", "material",
        ):
            setattr(self, name, getattr(data, name))

    def setInLaundry(self, value: bool) -> None:
        self.inLaundry = value

    def markDeleted(self) -> None:
        self.deleted = True

    def isAvailable(self) -> bool:
        return not self.deleted and not self.inLaundry

    def validate(self) -> None:
        if not self.type.strip() or not self.color.strip():
            raise ValidationError("Укажите тип и цвет вещи")
        if not self.seasons:
            raise ValidationError("Укажите хотя бы один сезон")
        if self.minTemperature > self.maxTemperature:
            raise ValidationError("Минимальная температура выше максимальной")

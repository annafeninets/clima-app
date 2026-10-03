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
        text_fields = (
            ("тип", self.type, 100),
            ("цвет", self.color, 100),
            ("повод", self.dressCode, 100),
            ("стиль", self.style, 100),
            ("силуэт", self.silhouette, 100),
            ("материал", self.material, 100),
        )
        for label, value, max_length in text_fields:
            if not isinstance(value, str):
                raise ValidationError(f"Поле «{label}» должно быть строкой")
            if len(value) > max_length:
                raise ValidationError(f"Поле «{label}» не должно превышать {max_length} символов")
        if not self.type.strip() or not self.color.strip():
            raise ValidationError("Укажите тип и цвет вещи")
        if not self.seasons:
            raise ValidationError("Укажите хотя бы один сезон")
        if any(not isinstance(season, Season) for season in self.seasons):
            raise ValidationError("Некорректный сезон")
        if (
            isinstance(self.minTemperature, bool)
            or not isinstance(self.minTemperature, int)
            or isinstance(self.maxTemperature, bool)
            or not isinstance(self.maxTemperature, int)
        ):
            raise ValidationError("Температура должна быть целым числом")
        if not isinstance(self.part, ItemPart):
            raise ValidationError("Некорректная часть одежды")
        if self.minTemperature > self.maxTemperature:
            raise ValidationError("Минимальная температура выше максимальной")

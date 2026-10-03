from dataclasses import dataclass, field

from clima.errors import ValidationError
from clima.models.entities.base import OwnedEntity
from clima.models.enums import ItemPart, Season

MIN_ITEM_TEMPERATURE = -50
MAX_ITEM_TEMPERATURE = 50
TOP_TYPE_MARKERS = (
    "футболк", "рубаш", "блуз", "свитер", "худи", "кардиган", "куртк", "пальто",
    "плащ", "пиджак", "жилет", "топ", "майк", "свитшот", "кофт", "жакет",
    "джемпер", "пуловер", "парка", "ветровк", "толстовк", "водолазк", "лонгслив",
    "футбол", "blouse", "sweater", "hoodie", "jacket", "coat",
)
BOTTOM_TYPE_MARKERS = (
    "джинс", "брюк", "штан", "юбк", "шорт", "леггинс", "лосин", "капри",
    "кроссов", "ботин", "сапог", "туфл", "сандал", "кед", "мокасин",
    "jean", "trouser", "pants", "skirt", "shorts", "legging", "shoe", "boot",
)


def expected_part_for_type(item_type: str) -> ItemPart | None:
    normalized = item_type.casefold().replace("ё", "е")
    is_top = any(marker in normalized for marker in TOP_TYPE_MARKERS)
    is_bottom = any(marker in normalized for marker in BOTTOM_TYPE_MARKERS)
    if is_top == is_bottom:
        return None
    return ItemPart.TOP if is_top else ItemPart.BOTTOM


@dataclass(slots=True)
class Item(OwnedEntity):
    photo: str = ""
    type: str = ""
    color: str = ""
    seasons: list[Season] = field(default_factory=list)
    minTemperature: int = MIN_ITEM_TEMPERATURE
    maxTemperature: int = MAX_ITEM_TEMPERATURE
    part: ItemPart = ItemPart.TOP
    dressCode: str = ""
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
            if not value.strip():
                raise ValidationError(f"Заполните поле «{label}»")
            if not any(character.isalpha() for character in value) or any(
                not character.isalpha() and not character.isdigit()
                and not character.isspace() and character not in ".,'’()/#%+-"
                for character in value
            ):
                raise ValidationError(f"Проверьте значение поля «{label}»")
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
        if not MIN_ITEM_TEMPERATURE <= self.minTemperature <= MAX_ITEM_TEMPERATURE:
            raise ValidationError("Минимальная температура должна быть от −50 до 50 °C")
        if not MIN_ITEM_TEMPERATURE <= self.maxTemperature <= MAX_ITEM_TEMPERATURE:
            raise ValidationError("Максимальная температура должна быть от −50 до 50 °C")
        if not isinstance(self.part, ItemPart):
            raise ValidationError("Некорректная часть одежды")
        expected_part = expected_part_for_type(self.type)
        if expected_part is None and any(
            marker in self.type.casefold().replace("ё", "е")
            for marker in TOP_TYPE_MARKERS
        ) and any(
            marker in self.type.casefold().replace("ё", "е")
            for marker in BOTTOM_TYPE_MARKERS
        ):
            raise ValidationError("Тип вещи не может одновременно относиться к верху и низу")
        if expected_part is not None and expected_part != self.part:
            raise ValidationError("Часть образа не соответствует типу вещи")
        if self.minTemperature > self.maxTemperature:
            raise ValidationError("Минимальная температура выше максимальной")

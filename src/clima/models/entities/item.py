from dataclasses import dataclass, field

from clima.errors import ValidationError
from clima.models.entities.base import OwnedEntity
from clima.models.enums import ItemPart, Season

MIN_ITEM_TEMPERATURE = -50
MAX_ITEM_TEMPERATURE = 50
TOP_TYPE_MARKERS = (
    "футболк", "поло", "лонгслив", "майк", "топ", "рубаш", "блуз", "туник", "корсет",
    "боди", "свитер", "худи", "кардиган", "куртк", "пальто", "плащ", "пиджак",
    "жилет", "свитшот", "толстовк", "жакет", "блейзер", "джемпер", "пуловер", "парка",
    "ветровк", "анорак", "пухов", "тренч", "дубл", "шуб", "водолазк", "бомбер",
    "футбол", "blouse", "sweater", "hoodie", "jacket", "coat",
)
BOTTOM_TYPE_MARKERS = (
    "джинс", "брюк", "штан", "юбк", "шорт", "бермуд", "леггинс", "лосин", "капри",
    "кроссов", "кед", "ботин", "ботильон", "сапог", "туфл", "лофер", "мокасин",
    "балет", "сандал", "босонож", "шлеп", "мюл", "угг", "jean", "trouser", "pants",
    "skirt", "shorts", "legging", "shoe", "boot",
)
SHOE_TYPE_MARKERS = (
    "кроссов", "кед", "ботин", "ботильон", "сапог", "туфл", "лофер", "мокасин",
    "балет", "сандал", "босонож", "шлеп", "мюл", "угг", "shoe", "boot",
)
ACCESSORY_TYPE_MARKERS = (
    "шарф", "шапк", "перчат", "носк", "колгот", "ремн", "сумк", "рюкзак",
    "клатч", "кошелек", "кошелёк", "scarf", "bag",
)
ONE_PIECE_TYPE_MARKERS = ("плать", "сарафан", "комбинезон", "dress", "jumpsuit")
SILHOUETTES_BY_CATEGORY = {
    "upper": (
        "прямой", "straight", "свободный", "приталенный", "oversize", "облегающий",
        "relaxed", "широкий", "оверсайз", "полуприлегающий", "слим", "slim fit",
        "regular fit", "свободный крой", "прямой крой", "укороченный", "удлиненный",
        "структурный", "на запах", "асимметричный",
    ),
    "lower": (
        "прямой", "straight", "свободный", "широкий", "облегающий", "relaxed", "skinny",
        "slim fit", "regular fit", "зауженный", "расклешенный", "клеш", "палаццо",
        "карго", "бананы", "мом", "бойфренд", "высокая посадка", "средняя посадка",
        "низкая посадка", "укороченный", "удлиненный", "карандаш", "трапеция", "плиссе",
    ),
    "onePiece": (
        "прямой", "свободный", "приталенный", "облегающий", "а-силуэт",
        "полуприлегающий", "карандаш", "трапеция", "солнце", "плиссе", "футляр",
        "баллон", "кокон", "тюльпан", "ампир", "принцесса", "миди", "макси", "мини",
        "на запах", "асимметричный",
    ),
    "footwear": (
        "кроссовки", "кеды", "ботинки", "ботильоны", "сапоги", "туфли", "лоферы",
        "балетки", "сандалии", "на каблуке", "на платформе", "на плоской подошве",
        "высокое голенище", "низкое голенище", "округлый нос", "острый нос",
        "квадратный нос", "массивная подошва", "минималистичные",
    ),
    "bag": (
        "тоут", "шоппер", "кросс-боди", "клатч", "сэтчел", "хобо", "сумка-ведро",
        "рюкзак", "мини-сумка", "структурная", "мягкая форма", "прямоугольная",
        "круглая", "полумесяц", "вытянутая", "компактная", "объемная",
    ),
    "scarf": (
        "длинный", "короткий", "широкий", "узкий", "треугольный", "квадратный",
        "палантин", "снуд", "на запах", "объемный", "легкий", "плотный",
    ),
    "accessory": (
        "бини", "бейсболка", "панама", "берет", "кепка", "широкополая", "длинные",
        "короткие", "высокие", "низкие", "широкий", "узкий", "классический", "компактный",
    ),
}


def expected_part_for_type(item_type: str) -> ItemPart | None:
    normalized = item_type.casefold().replace("ё", "е")
    if any(marker in normalized for marker in SHOE_TYPE_MARKERS):
        return ItemPart.SHOES
    if any(marker in normalized for marker in ACCESSORY_TYPE_MARKERS):
        return ItemPart.ACCESSORY
    if any(marker in normalized for marker in ONE_PIECE_TYPE_MARKERS):
        return ItemPart.ONE_PIECE
    is_top = any(marker in normalized for marker in TOP_TYPE_MARKERS)
    is_bottom = any(marker in normalized for marker in BOTTOM_TYPE_MARKERS)
    if is_top and is_bottom and "куртк" in normalized and "джинс" in normalized:
        return ItemPart.TOP
    if is_top == is_bottom:
        return None
    return ItemPart.TOP if is_top else ItemPart.BOTTOM


def silhouette_category_for_type(item_type: str) -> str:
    normalized = item_type.casefold().replace("ё", "е")
    if any(marker in normalized for marker in SHOE_TYPE_MARKERS):
        return "footwear"
    if any(marker in normalized for marker in ("сумк", "рюкзак", "клатч", "кошелек", "кошелёк", "bag")):
        return "bag"
    if any(marker in normalized for marker in ("шарф", "scarf")):
        return "scarf"
    if any(marker in normalized for marker in ("шапк", "перчат", "носк", "колгот", "ремн")):
        return "accessory"
    if any(marker in normalized for marker in ONE_PIECE_TYPE_MARKERS):
        return "onePiece"
    if any(marker in normalized for marker in BOTTOM_TYPE_MARKERS):
        return "lower"
    return "upper"


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
        if not isinstance(self.type, str):
            raise ValidationError("Поле «тип» должно быть строкой")
        silhouette_options = SILHOUETTES_BY_CATEGORY[silhouette_category_for_type(self.type)]
        text_fields = (
            ("тип", self.type, 100, False),
            ("цвет", self.color, 100, False),
            ("повод", self.dressCode, 100, False),
            ("стиль", self.style, 100, False),
            ("силуэт", self.silhouette, 100, False),
            ("материал", self.material, 100, False),
        )
        for label, value, max_length, optional in text_fields:
            if not isinstance(value, str):
                raise ValidationError(f"Поле «{label}» должно быть строкой")
            if len(value) > max_length:
                raise ValidationError(f"Поле «{label}» не должно превышать {max_length} символов")
            if not value.strip():
                if optional:
                    continue
                raise ValidationError(f"Заполните поле «{label}»")
            if not any(character.isalpha() for character in value) or any(
                not character.isalpha() and not character.isdigit()
                and not character.isspace() and character not in ".,'’()/#%+-"
                for character in value
            ):
                raise ValidationError(f"Проверьте значение поля «{label}»")
            if label == "силуэт" and value.casefold().replace("ё", "е") not in silhouette_options:
                raise ValidationError("Силуэт не подходит к выбранному типу вещи")
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
            raise ValidationError("Выбранная часть образа не соответствует типу вещи")
        if self.minTemperature > self.maxTemperature:
            raise ValidationError("Минимальная температура выше максимальной")

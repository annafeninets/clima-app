"""Правила сочетаемости одежды: погода, повод, цвет, формальность, материалы.

Генератор образов обязан пропускать каждого кандидата через этот модуль —
нельзя полагаться только на эвристики или LLM.

Модель погоды
-------------
Каждая вещь в справочнике ``CLOTHING_CATALOG`` имеет «теплоту» (``warmth``,
условные баллы). Сумма теплоты образа должна попадать в диапазон, который
задан для температурного диапазона (по ощущаемой температуре) в
``BAND_RULES``:

* ``absolute_min`` — ниже этого образ противоречит погоде и не показывается
  никогда (например, футболка + джинсы + пуховик при −12 °C);
* ``comfort_min``  — комфортный минимум; образы выше него идут первыми,
  остальные (но не ниже ``absolute_min``) добавляются, только если «комфортных»
  меньше трёх, и помечаются в debug как ``comfortable: false``;
* ``max``          — выше этого образ слишком тёплый (свитер + куртка в жару).

Запретные типы одежды (``forbidden``) действуют всегда.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import lru_cache
from itertools import product

from clima.models.entities import Item, Outfit, Preferences
from clima.models.entities.item import accessory_category_for_type, expected_part_for_type
from clima.models.enums import ItemPart, Season
from clima.models.value_objects import CheckResult, WeatherData

class Occasion(StrEnum):
    EVERYDAY = "everyday"
    CASUAL = "casual"
    WORK = "work"
    SPORT = "sport"
    DATE = "date"
    FORMAL = "formal"
    TRAVEL = "travel"
    PARTY = "party"
    OUTDOOR = "outdoor"

class TemperatureBand(StrEnum):
    HOT = "hot"          # > 28
    WARM = "warm"        # 20–28
    MILD = "mild"        # 12–20
    CHILLY = "chilly"    # 5–12
    COLD = "cold"        # −5–5
    FREEZING = "freezing"  # < −5

# Справочник типов: категория, сезонность, формальность 1–5, теплота, материалы, маркеры.
# Порядок важен: более специфичные типы стоят раньше («sweatshirt» раньше «shirt»).
CLOTHING_CATALOG: dict[str, dict] = {
    "t-shirt": {
        "category": "top", "seasons": ("SUMMER", "SPRING"), "formality": 2, "warmth": 1,
        "materials": ("cotton", "linen"), "markers": ("футболк", "t-shirt", "tee"),
        "compatible": ("bottom", "shoes", "outerwear", "accessory"),
    },
    "hoodie": {
        "category": "top", "seasons": ("AUTUMN", "SPRING", "WINTER"), "formality": 1, "warmth": 3,
        "materials": ("cotton", "fleece"),
        "markers": ("худи", "толстовк", "свитшот", "hoodie", "sweatshirt"),
        "compatible": ("bottom", "shoes", "outerwear", "accessory"),
    },
    # Свитер: формальность 2 → 3 (не футболка, носится под пиджак)
    "sweater": {
        "category": "top", "seasons": ("AUTUMN", "WINTER", "SPRING"), "formality": 3, "warmth": 3,
        "materials": ("wool", "knit", "cashmere"),
        "markers": ("свитер", "джемпер", "пуловер", "водолазк", "sweater", "jumper"),
        "compatible": ("bottom", "shoes", "outerwear", "accessory"),
    },
    "cardigan": {
        "category": "top", "seasons": ("SPRING", "AUTUMN"), "formality": 3, "warmth": 2,
        "materials": ("knit", "wool", "cotton"), "markers": ("кардиган", "cardigan"),
        "compatible": ("bottom", "shoes", "outerwear", "accessory"),
    },
    "top": {
        "category": "top", "seasons": ("SUMMER", "SPRING"), "formality": 2, "warmth": 1,
        "materials": ("cotton", "silk"), "markers": ("топ", "майк", "tank"),
        "compatible": ("bottom", "shoes", "outerwear", "accessory"),
    },
    "shirt": {
        "category": "top", "seasons": ("SPRING", "SUMMER", "AUTUMN"), "formality": 3, "warmth": 1,
        "materials": ("cotton", "linen"), "markers": ("рубаш", "shirt", "блуз", "blouse"),
        "compatible": ("bottom", "shoes", "outerwear", "accessory"),
    },
    "shorts": {
        "category": "bottom", "seasons": ("SUMMER",), "formality": 1, "warmth": 0,
        "materials": ("cotton", "linen"), "markers": ("шорт", "бермуд", "shorts"),
        "compatible": ("top", "shoes", "accessory"),
    },
    "skirt": {
        "category": "bottom", "seasons": ("SPRING", "SUMMER", "AUTUMN"), "formality": 3, "warmth": 1,
        "materials": ("cotton", "wool", "silk"), "markers": ("юбк", "skirt"),
        "compatible": ("top", "shoes", "outerwear", "accessory"),
    },
    "jeans": {
        "category": "bottom", "seasons": ("SPRING", "AUTUMN", "WINTER", "SUMMER"), "formality": 2,
        "warmth": 2, "materials": ("denim",), "markers": ("джинс", "jeans"),
        "compatible": ("top", "shoes", "outerwear", "accessory"),
    },
    "insulated-pants": {
        "category": "bottom", "seasons": ("WINTER",), "formality": 1, "warmth": 4,
        "materials": ("fleece", "nylon"), "markers": ("утеплен", "утеплён", "термо"),
        "compatible": ("top", "shoes", "outerwear", "accessory"),
    },
    "pants": {
        "category": "bottom", "seasons": ("SPRING", "AUTUMN", "WINTER", "SUMMER"), "formality": 3,
        "warmth": 2, "materials": ("cotton", "wool", "polyester"),
        "markers": ("брюк", "штан", "trousers", "pants", "леггинс", "лосин"),
        "compatible": ("top", "shoes", "outerwear", "accessory"),
    },
    "raincoat": {
        "category": "outerwear", "seasons": ("SPRING", "AUTUMN", "SUMMER"), "formality": 2,
        "warmth": 1, "materials": ("nylon", "membrane"),
        "markers": ("дождевик", "плащ", "raincoat", "водонепроница"),
        "compatible": ("top", "bottom", "shoes", "accessory"),
    },
    "down-coat": {
        "category": "outerwear", "seasons": ("WINTER",), "formality": 2, "warmth": 6,
        "materials": ("down", "nylon"), "markers": ("пухов", "парка", "parka", "down"),
        "compatible": ("top", "bottom", "shoes", "accessory"),
    },
    "coat": {
        "category": "outerwear", "seasons": ("AUTUMN", "WINTER"), "formality": 4, "warmth": 4,
        "materials": ("wool", "cashmere"), "markers": ("пальто", "тренч", "coat", "trench"),
        "compatible": ("top", "bottom", "shoes", "accessory"),
    },
    # Блейзер: формальность 5 → 4 (формальный, но не black tie)
    "blazer": {
        "category": "outerwear", "seasons": ("SPRING", "AUTUMN", "SUMMER"), "formality": 4,
        "warmth": 2, "materials": ("wool", "cotton"),
        "markers": ("пиджак", "блейзер", "жакет", "blazer"),
        "compatible": ("top", "bottom", "shoes", "accessory"),
    },
    "jacket": {
        "category": "outerwear", "seasons": ("SPRING", "AUTUMN"), "formality": 3, "warmth": 2,
        "materials": ("cotton", "nylon", "denim"),
        "markers": ("куртк", "ветровк", "бомбер", "косух", "jacket", "bomber"),
        "compatible": ("top", "bottom", "shoes", "accessory"),
    },
    "winter-boots": {
        "category": "shoes", "seasons": ("WINTER",), "formality": 2, "warmth": 4,
        "materials": ("leather", "rubber"), "markers": ("угг", "зимн", "валенк", "дутик"),
        "compatible": ("top", "bottom", "outerwear", "accessory"),
    },
    "boots": {
        "category": "shoes", "seasons": ("AUTUMN", "WINTER"), "formality": 3, "warmth": 2,
        "materials": ("leather", "suede"), "markers": ("ботин", "ботильон", "сапог", "boots"),
        "compatible": ("top", "bottom", "outerwear", "accessory"),
    },
    "dress-shoes": {
        "category": "shoes", "seasons": ("SPRING", "AUTUMN", "WINTER", "SUMMER"), "formality": 5,
        "warmth": 1, "materials": ("leather",),
        "markers": ("туфл", "оксфорд", "дерби", "балетк"),
        "compatible": ("top", "bottom", "outerwear", "accessory"),
    },
    "loafers": {
        "category": "shoes", "seasons": ("SPRING", "SUMMER", "AUTUMN"), "formality": 4, "warmth": 1,
        "materials": ("leather",), "markers": ("лофер", "мокасин", "loafers"),
        "compatible": ("top", "bottom", "outerwear", "accessory"),
    },
    "sandals": {
        "category": "shoes", "seasons": ("SUMMER",), "formality": 1, "warmth": 0,
        "materials": ("leather", "rubber"), "markers": ("сандал", "босонож", "шлеп", "sandals"),
        "compatible": ("top", "bottom", "accessory"),
    },
    "sneakers": {
        "category": "shoes", "seasons": ("SPRING", "SUMMER", "AUTUMN"), "formality": 2, "warmth": 1,
        "materials": ("mesh", "leather", "suede"),
        "markers": ("кроссов", "кед", "sneakers", "trainers"),
        "compatible": ("top", "bottom", "outerwear", "accessory"),
    },
    "dress": {
        "category": "one_piece", "seasons": ("SPRING", "SUMMER", "AUTUMN"), "formality": 4,
        "warmth": 2, "materials": ("cotton", "silk", "wool"),
        "markers": ("плать", "сарафан", "dress"),
        "compatible": ("shoes", "outerwear", "accessory"),
    },
    "jumpsuit": {
        "category": "one_piece", "seasons": ("SPRING", "SUMMER"), "formality": 3, "warmth": 2,
        "materials": ("cotton",), "markers": ("комбинезон", "jumpsuit"),
        "compatible": ("shoes", "outerwear", "accessory"),
    },
    "hat": {
        "category": "accessory", "seasons": ("WINTER",), "formality": 1, "warmth": 1,
        "materials": ("wool", "knit"), "markers": ("шапк", "бини", "beanie"),
        "compatible": ("top", "bottom", "shoes", "outerwear"),
    },
    "scarf": {
        "category": "accessory", "seasons": ("AUTUMN", "WINTER"), "formality": 2, "warmth": 1,
        "materials": ("wool", "knit", "silk"), "markers": ("шарф", "снуд", "палантин", "scarf"),
        "compatible": ("top", "bottom", "shoes", "outerwear"),
    },
    "gloves": {
        "category": "accessory", "seasons": ("WINTER",), "formality": 2, "warmth": 1,
        "materials": ("wool", "leather"), "markers": ("перчат", "варежк", "gloves"),
        "compatible": ("top", "bottom", "shoes", "outerwear"),
    },
    "sunglasses": {
        "category": "accessory", "seasons": ("SUMMER", "SPRING"), "formality": 2, "warmth": 0,
        "materials": ("plastic", "metal"), "markers": ("очк", "sunglasses"),
        "compatible": ("top", "bottom", "shoes", "outerwear"),
    },
    "umbrella": {
        "category": "accessory", "seasons": ("SPRING", "AUTUMN", "SUMMER"), "formality": 2,
        "warmth": 0, "materials": ("nylon",), "markers": ("зонт", "umbrella"),
        "compatible": ("top", "bottom", "shoes", "outerwear"),
    },
    "cap": {
        "category": "accessory", "seasons": ("SUMMER", "SPRING"), "formality": 1, "warmth": 0,
        "materials": ("cotton",), "markers": ("кепк", "бейсболк", "панам", "шляп", "cap", "hat"),
        "compatible": ("top", "bottom", "shoes", "outerwear"),
    },
    "bag": {
        "category": "accessory", "seasons": ("SPRING", "SUMMER", "AUTUMN", "WINTER"), "formality": 3,
        "warmth": 0, "materials": ("leather", "canvas"),
        "markers": ("сумк", "рюкзак", "клатч", "bag", "backpack"),
        "compatible": ("top", "bottom", "shoes", "outerwear"),
    },
}

_FALLBACK_BY_PART = {
    ItemPart.TOP: {"key": "shirt", "category": "top", "formality": 2, "warmth": 1},
    ItemPart.BOTTOM: {"key": "pants", "category": "bottom", "formality": 2, "warmth": 2},
    ItemPart.SHOES: {"key": "sneakers", "category": "shoes", "formality": 2, "warmth": 1},
    ItemPart.OUTERWEAR: {"key": "jacket", "category": "outerwear", "formality": 3, "warmth": 2},
    ItemPart.ACCESSORY: {"key": "bag", "category": "accessory", "formality": 2, "warmth": 0},
    ItemPart.ONE_PIECE: {"key": "dress", "category": "one_piece", "formality": 3, "warmth": 2},
}
_CATEGORY_BY_PART = {
    ItemPart.TOP: "top", ItemPart.BOTTOM: "bottom", ItemPart.SHOES: "shoes",
    ItemPart.OUTERWEAR: "outerwear", ItemPart.ACCESSORY: "accessory",
    ItemPart.ONE_PIECE: "one_piece",
}

SUMMER_MATERIALS = {
    "linen", "лён", "лен", "chiffon", "шифон", "cotton", "хлопок", "silk", "шёлк", "шелк",
}
WINTER_MATERIALS = {
    "wool", "шерсть", "down", "пух", "fleece", "флис", "fur", "мех", "cashmere", "кашемир",
}
SPORT_MATERIALS = (
    "polyester", "полиэстер", "nylon", "нейлон", "elastane", "эластан", "spandex",
    "mesh", "сетк", "microfiber", "микрофибр", "dri-fit", "спортив",
)
WATERPROOF_MARKERS = (
    "дождевик", "непромока", "водонепроница", "raincoat", "waterproof", "мембран", "membrane",
    "резин", "rubber",
)
NEUTRAL_COLORS = {"black", "white", "gray", "beige", "brown", "navy", "cream"}
LARGE_PATTERNS = ("клетк", "полоск", "принт", "леопард", "цветоч", "check", "stripe", "print")

# Спорт: эти типы допустимы без пометки «спортивный»; всё остальное — только спортивное.
SPORT_NEUTRAL_KEYS = {
    "t-shirt", "top", "hoodie", "shorts", "insulated-pants", "sneakers", "raincoat",
    "down-coat", "jacket",
}

OCCASION_ALIASES = {
    "everyday": "everyday", "casual": "casual", "повседневный": "everyday",
    "на каждый день": "everyday", "work": "work", "работа": "work", "офис": "work",
    "business": "work", "sport": "sport", "спорт": "sport", "date": "date",
    "свидание": "date", "formal": "formal", "торжественный": "formal",
    "вечерний": "formal", "party": "party", "вечеринка": "party", "travel": "travel",
    "путешествие": "travel", "outdoor": "outdoor", "прогулка": "outdoor",
    "прогулка / outdoor": "outdoor",
}
OCCASION_ALIASES = {key: Occasion(value) for key, value in OCCASION_ALIASES.items()}

# Минимальная формальность неаксессуарных вещей по поводу.
OCCASION_MIN_FORMALITY = {
    Occasion.FORMAL: 3, Occasion.WORK: 2, Occasion.PARTY: 2,
}
# Типы, запрещённые для повода.
OCCASION_FORBIDDEN_KEYS: dict[Occasion, frozenset[str]] = {
    Occasion.FORMAL: frozenset({
        "sneakers", "shorts", "hoodie", "cap", "sandals", "t-shirt", "jeans",
        "insulated-pants", "winter-boots",
    }),
    Occasion.WORK: frozenset({"shorts", "hoodie", "sandals", "cap", "insulated-pants"}),
    Occasion.TRAVEL: frozenset({"dress-shoes", "blazer"}),
    Occasion.OUTDOOR: frozenset({"dress-shoes", "sandals", "loafers", "blazer", "dress"}),
}

@dataclass(frozen=True, slots=True)
class BandRule:
    """Правило температурного диапазона (по ощущаемой температуре)."""

    label: str
    layers: str
    top: str
    bottom: str
    shoes: str
    accessories: str
    absolute_min: int
    comfort_min: int
    max: int
    forbidden: frozenset[str]

BAND_RULES: dict[TemperatureBand, BandRule] = {
    TemperatureBand.HOT: BandRule(
        "> 28 °C", "1", "лёгкая футболка/топ", "шорты/лёгкая юбка", "сандалии/кроссовки",
        "панама, очки", absolute_min=0, comfort_min=0, max=6,
        forbidden=frozenset({
            "sweater", "hoodie", "cardigan", "jacket", "coat", "down-coat", "insulated-pants",
            "boots", "winter-boots", "hat", "gloves", "scarf",
        }),
    ),
    TemperatureBand.WARM: BandRule(
        "20–28 °C", "1–2", "футболка/рубашка", "брюки/джинсы/юбка", "кроссовки/лоферы", "кепка",
        absolute_min=1, comfort_min=2, max=7,
        forbidden=frozenset({
            "sweater", "coat", "down-coat", "insulated-pants", "winter-boots", "hat", "gloves",
            "scarf",
        }),
    ),
    TemperatureBand.MILD: BandRule(
        "12–20 °C", "2", "рубашка + лёгкая куртка/кардиган", "джинсы/брюки",
        "кроссовки/ботинки", "—", absolute_min=3, comfort_min=5, max=13,
        forbidden=frozenset({
            "down-coat", "winter-boots", "insulated-pants", "shorts", "sandals", "hat", "gloves",
        }),
    ),
    TemperatureBand.CHILLY: BandRule(
        "5–12 °C", "3", "свитер + куртка", "плотные брюки", "ботинки", "шарф",
        absolute_min=6, comfort_min=8, max=17,
        forbidden=frozenset({"shorts", "sandals", "cap", "sunglasses"}),
    ),
    TemperatureBand.COLD: BandRule(
        "−5…5 °C", "3–4", "термобельё + пуховик", "утеплённые брюки", "зимние ботинки",
        "шапка, шарф, перчатки", absolute_min=9, comfort_min=11, max=28,
        forbidden=frozenset({"shorts", "sandals", "loafers", "cap", "sunglasses"}),
    ),
    TemperatureBand.FREEZING: BandRule(
        "< −5 °C", "4", "термо + пуховик/парка", "термо + утеплённые брюки", "зимние ботинки",
        "полный набор", absolute_min=12, comfort_min=14, max=99,
        forbidden=frozenset({
            "shorts", "sandals", "loafers", "cap", "sunglasses", "sneakers", "dress-shoes",
        }),
    ),
}

# Мягкие предпочтения диапазона (строки таблицы из ТЗ): каждый подходящий тип даёт бонус к оценке.
BAND_PREFERRED: dict[TemperatureBand, frozenset[str]] = {
    TemperatureBand.HOT: frozenset({
        "t-shirt", "top", "shorts", "skirt", "dress", "sandals", "sneakers", "cap", "sunglasses",
    }),
    TemperatureBand.WARM: frozenset({
        "t-shirt", "shirt", "jeans", "pants", "skirt", "dress", "sneakers", "loafers", "cap",
    }),
    TemperatureBand.MILD: frozenset({
        "shirt", "cardigan", "jacket", "jeans", "pants", "sneakers", "boots",
    }),
    TemperatureBand.CHILLY: frozenset({
        "sweater", "jacket", "coat", "pants", "boots", "scarf",
    }),
    TemperatureBand.COLD: frozenset({
        "sweater", "coat", "down-coat", "insulated-pants", "winter-boots", "boots", "hat",
        "scarf", "gloves",
    }),
    TemperatureBand.FREEZING: frozenset({
        "down-coat", "insulated-pants", "winter-boots", "hat", "scarf", "gloves", "sweater",
    }),
}
PREFERRED_BONUS = 5
# Повод «работа»: за каждую вещь уровня smart casual и выше — бонус.
WORK_FORMAL_BONUS = 4

@dataclass(slots=True)
class WeatherProfile:
    place: str
    date: date
    temperature: int
    feels_like: int
    conditions: str
    wind: float = 0.0
    humidity: int = 0
    precipitation: float = 0.0
    uv: float = 0.0
    band: TemperatureBand = TemperatureBand.MILD
    source: str = "forecast"

@dataclass(frozen=True, slots=True)
class ItemFacts:
    """Предвычисленные свойства вещи — считаются один раз на вещь."""

    key: str
    category: str
    warmth: int
    formality: int
    sporty: bool
    color: str
    neutral: bool
    pattern: bool
    waterproof: bool

def normalize_occasion(value: str | None) -> Occasion:
    key = (value or "everyday").strip().casefold()
    return OCCASION_ALIASES.get(key, Occasion.EVERYDAY)

def wind_chill(temperature: float, wind_kmh: float) -> int:
    if temperature > 10 or wind_kmh < 5:
        return round(temperature)
    return round(
        13.12 + 0.6215 * temperature
        - 11.37 * (wind_kmh ** 0.16)
        + 0.3965 * temperature * (wind_kmh ** 0.16)
    )

def band_for_feels_like(feels_like: int) -> TemperatureBand:
    if feels_like > 28:
        return TemperatureBand.HOT
    if feels_like >= 20:
        return TemperatureBand.WARM
    if feels_like >= 12:
        return TemperatureBand.MILD
    if feels_like >= 5:
        return TemperatureBand.CHILLY
    if feels_like >= -5:
        return TemperatureBand.COLD
    return TemperatureBand.FREEZING

def profile_from_weather(weather: WeatherData) -> WeatherProfile:
    feels = weather.feelsLike if weather.feelsLike is not None else wind_chill(
        weather.temperature, weather.windSpeed
    )
    conditions = weather.conditions.casefold()
    precipitation = weather.precipitation
    if precipitation <= 0 and any(
        word in conditions for word in ("дожд", "лив", "rain", "drizzle", "снег", "snow", "морос")
    ):
        precipitation = max(precipitation, 1.0)
    return WeatherProfile(
        place=weather.place,
        date=weather.date,
        temperature=weather.temperature,
        feels_like=int(feels),
        conditions=weather.conditions,
        wind=weather.windSpeed,
        humidity=weather.humidity,
        precipitation=precipitation,
        uv=weather.uvIndex,
        band=band_for_feels_like(int(feels)),
        source=weather.source,
    )

def season_for(day: date, latitude: float | None = None) -> Season:
    """Сезон по дате с учётом полушария: в южном полушарии сезоны сдвинуты на полгода."""
    month = day.month
    if latitude is not None and latitude < 0:
        month = (month + 5) % 12 + 1
    if month in (12, 1, 2):
        return Season.WINTER
    if month in (3, 4, 5):
        return Season.SPRING
    if month in (6, 7, 8):
        return Season.SUMMER
    return Season.AUTUMN

def _normalize(text: str) -> str:
    return (text or "").casefold().replace("ё", "е")

def catalog_entry_for(item: Item) -> dict:
    """Запись справочника для вещи.

    Сначала ищем среди записей той же категории, что и часть образа (так
    «джинсовая куртка» не станет «джинсами»), и только по названию типа —
    стиль и материал в классификации не участвуют.
    """
    text = _normalize(item.type)
    wanted = _CATEGORY_BY_PART.get(item.part)
    pools = (
        [(k, e) for k, e in CLOTHING_CATALOG.items() if e["category"] == wanted],
        list(CLOTHING_CATALOG.items()),
    )
    for pool in pools:
        for key, entry in pool:
            if any(marker in text for marker in entry["markers"]):
                return {"key": key, **entry}
    fallback = _FALLBACK_BY_PART[item.part]
    return {"seasons": (), "materials": (), "compatible": (), **fallback}

def formality_of(item: Item) -> int:
    code = _normalize(item.dressCode)
    entry = catalog_entry_for(item)
    # Ищем в каталоге только те вещи, что действительно распознаны по маркерам,
    # а не через fallback. У fallback ключ есть, но seasons/materials пустые.
    if entry.get("key") in CLOTHING_CATALOG and entry.get("markers"):
        base = int(entry["formality"])
        if any(word in code for word in ("sport", "спорт")):
            return 1
        if any(word in code for word in ("formal", "торже", "вечер", "black tie")):
            return max(base, 4)
        if any(word in code for word in ("work", "office", "офис", "smart")):
            return max(base, 3)
        return base
    # Fallback — вещь не распознана каталогом, доверяем dressCode.
    if any(word in code for word in ("formal", "торже", "вечер", "black tie", "business")):
        return 5
    if any(word in code for word in ("work", "office", "офис", "smart")):
        return 4
    if any(word in code for word in ("sport", "спорт")):
        return 1
    return 2

@lru_cache(maxsize=8192)
def _facts(
    item_type: str, part: ItemPart, color: str, material: str, style: str, dress_code: str,
    canonical_color: str,
) -> ItemFacts:
    probe = Item(type=item_type, part=part, color=color, material=material,
                 style=style, dressCode=dress_code)
    entry = catalog_entry_for(probe)
    material_text = _normalize(material)
    warmth = int(entry["warmth"])
    if entry["category"] in {"top", "bottom", "outerwear"} and any(
        token in material_text for token in WINTER_MATERIALS
    ):
        warmth += 1
    text = _normalize(f"{item_type} {style} {dress_code} {material}")
    sporty = any(word in _normalize(f"{dress_code} {style}") for word in ("sport", "спорт")) or any(
        token in material_text for token in SPORT_MATERIALS
    )
    is_denim = "denim" in material_text or "джинс" in material_text or entry["key"] == "jeans"
    pattern = any(marker in _normalize(f"{item_type} {style}") for marker in LARGE_PATTERNS)
    return ItemFacts(
        key=entry["key"], category=entry["category"], warmth=warmth,
        formality=formality_of(probe), sporty=sporty, color=canonical_color,
        neutral=(not canonical_color) or canonical_color in NEUTRAL_COLORS or is_denim,
        pattern=pattern,
        waterproof=any(marker in text for marker in WATERPROOF_MARKERS),
    )

def should_suggest_outerwear(profile: WeatherProfile) -> bool:
    if profile.band in {
        TemperatureBand.MILD, TemperatureBand.CHILLY, TemperatureBand.COLD, TemperatureBand.FREEZING,
    }:
        return True
    return profile.precipitation >= 0.2 or profile.wind >= 28

def should_suggest_scarf(profile: WeatherProfile) -> bool:
    return profile.band in {TemperatureBand.CHILLY, TemperatureBand.COLD, TemperatureBand.FREEZING}

def should_suggest_sun(profile: WeatherProfile) -> bool:
    return profile.uv >= 5 or profile.band in {TemperatureBand.HOT, TemperatureBand.WARM}

class CompatibilityRule:
    maxVariants = 3
    colorAliases = {
        "red": {"red", "красный", "красная", "красное", "красные", "бордовый", "бордовая"},
        "green": {"green", "зеленый", "зелёный", "зеленая", "зелёная", "зеленое", "зелёное"},
        "orange": {"orange", "оранжевый", "оранжевая", "оранжевое"},
        "pink": {"pink", "розовый", "розовая", "розовое", "розовые"},
        "blue": {"blue", "синий", "синяя", "синее", "голубой", "голубая", "голубое"},
        "purple": {"purple", "фиолетовый", "фиолетовая", "фиолетовое"},
        "yellow": {"yellow", "желтый", "жёлтый", "желтая", "жёлтая", "желтое", "жёлтое"},
        "black": {"black", "черный", "чёрный", "черная", "чёрная", "черное", "чёрное"},
        "white": {"white", "белый", "белая", "белое"},
        "gray": {"gray", "grey", "серый", "серая", "серое"},
        "beige": {"beige", "бежевый", "бежевая", "бежевое"},
        "cream": {"cream", "ivory", "молочный", "кремовый", "молочная", "кремовая"},
        "brown": {"brown", "коричневый", "коричневая", "коричневое"},
        "navy": {"navy", "темно-синий", "тёмно-синий", "тёмно-синяя", "темно-синяя"},
    }
    incompatiblePairs = {
        frozenset(("red", "green")),
        frozenset(("orange", "pink")),
        frozenset(("blue", "orange")),
        frozenset(("purple", "yellow")),
    }
    _neutrals = NEUTRAL_COLORS
    _dresses = {"dress", "jumpsuit", "комбинезон", "платье"}
    _scarves = ("шарф", "scarf")

    # ------------------------------------------------------------------ facts

    def _facts(self, item: Item) -> ItemFacts:
        return _facts(
            item.type, item.part, item.color, item.material, item.style, item.dressCode,
            self._canonicalColor(item.color),
        )

    # ------------------------------------------------------------------ check

    def check(self, items: list[Item]) -> CheckResult:
        """Структурная сочетаемость (без учёта погоды): слоты, цвета, паттерны, материалы."""
        available = [item for item in items if item.isAvailable()]
        if not available:
            return CheckResult(False, "Нет доступных вещей")
        one_pieces = [item for item in available if self._isOnePiece(item)]
        if len(one_pieces) > 1:
            return CheckResult(False, "В образе может быть только одно платье или комбинезон")
        tops = [
            item for item in available
            if item.part == ItemPart.TOP and not self._isOuterwear(item)
            and not self._isOnePiece(item)
        ]
        bottoms = [item for item in available if item.part == ItemPart.BOTTOM]
        shoes = [item for item in available if item.part == ItemPart.SHOES]
        outerwear = [item for item in available if self._isOuterwear(item)]
        if len(tops) > 1:
            return CheckResult(False, "В образе может быть только один верх")
        if len(bottoms) > 1:
            return CheckResult(False, "В образе может быть только один низ")
        if len(shoes) > 1:
            return CheckResult(False, "В образе может быть только одна пара обуви")
        if len(outerwear) > 1:
            return CheckResult(False, "В образе может быть только одна вещь верхней одежды")
        accessory_categories = [
            accessory_category_for_type(item.type)
            for item in available if item.part == ItemPart.ACCESSORY
        ]
        if len(accessory_categories) != len(set(accessory_categories)):
            return CheckResult(
                False, "Нельзя сочетать два аксессуара одного типа "
                "(например, две сумки, два шарфа или две шапки)"
            )
        if one_pieces:
            core = [item for item in available if not self._isOnePiece(item)]
            if any(
                item.part in (ItemPart.TOP, ItemPart.BOTTOM) and not self._isOuterwear(item)
                for item in core
            ):
                return CheckResult(False, "Платье или комбинезон нельзя сочетать с верхом или низом")
        else:
            if not tops or not bottoms:
                return CheckResult(False, "Для образа нужны верх и низ или платье")
        if not shoes:
            return CheckResult(False, "Для полностью одетого образа нужна обувь")
        facts = [(item, self._facts(item)) for item in available]
        main_colors = {f.color for item, f in facts if item.part != ItemPart.ACCESSORY and f.color}
        if len(main_colors) > 3:
            return CheckResult(False, "В образе не больше трёх основных цветов")
        colors = [f.color for _, f in facts]
        for index, first in enumerate(colors):
            for second in colors[index + 1:]:
                if first not in self._neutrals and second not in self._neutrals:
                    if frozenset((first, second)) in self.incompatiblePairs:
                        return CheckResult(
                            False, f"Цвета «{first}» и «{second}» плохо сочетаются"
                        )
        if sum(1 for _, f in facts if f.pattern) > 1:
            return CheckResult(False, "В образе допустим только один крупный паттерн")
        materials = " ".join(_normalize(item.material) for item in available)
        has_summer = any(token in materials for token in SUMMER_MATERIALS)
        has_winter = any(token in materials for token in WINTER_MATERIALS)
        keys = {f.key for _, f in facts}
        if has_summer and has_winter and keys & {"shorts", "sandals"}:
            return CheckResult(False, "Не смешивайте зимние и летние материалы в одном образе")
        return CheckResult(True, "")

    # ---------------------------------------------------------- weather check

    def weatherCheck(
        self, items: list[Item], weather: WeatherData, occasion: str = "everyday",
        strict: bool = False,
    ) -> CheckResult:
        """Погода + повод + формальность поверх структурной проверки.

        ``strict=False`` — жёсткие запреты (противоречие погоде/поводу);
        ``strict=True`` — ещё и «комфортные» требования: теплота не ниже
        комфортного минимума, формальность ±1, нейтральная база + один акцент.
        """
        base = self.check(items)
        if not base.compatible:
            return base
        profile = profile_from_weather(weather)
        return self._weatherReason(items, profile, normalize_occasion(occasion), strict)

    def _weatherReason(
        self, items: list[Item], profile: WeatherProfile, occ: Occasion, strict: bool,
    ) -> CheckResult:
        rule = BAND_RULES[profile.band]
        reasons: list[str] = []
        facts = [(item, self._facts(item)) for item in items]
        for item, fact in facts:
            if not self._itemFitsOccasion(item, occ):
                reasons.append(f"{item.type}: не подходит для повода {occ.value}")
            if self._itemConflictsWeather(item, profile):
                reasons.append(
                    f"{item.type}: не подходит для {profile.band.value} ({profile.feels_like}°C)"
                )
        warmth = sum(f.warmth for _, f in facts)
        minimum = rule.comfort_min if strict else rule.absolute_min
        if warmth < minimum:
            reasons.append(
                f"слишком холодно для такого набора: теплота {warmth}, нужно не меньше {minimum}"
            )
        if warmth > rule.max:
            reasons.append(f"слишком тепло одет: теплота {warmth}, не больше {rule.max}")
        formalities = [f.formality for item, f in facts if item.part != ItemPart.ACCESSORY]
        if formalities and max(formalities) - min(formalities) > (1 if strict else 2):
            reasons.append("уровень формальности вещей слишком разный")
        accents = {f.color for _, f in facts if not f.neutral}
        if len(accents) > (1 if strict else 2):
            reasons.append("нужна нейтральная база и не больше одного акцентного цвета")
        if reasons:
            return CheckResult(False, "; ".join(reasons))
        return CheckResult(True, "")

    # ------------------------------------------------------------------ score

    def match(self, items: list[Item], weather: WeatherData, occasion: str) -> int:
        result = self.weatherCheck(items, weather, occasion)
        if not result.compatible:
            return 0
        return self._score(items, profile_from_weather(weather), normalize_occasion(occasion),
                           weather.temperature, occasion)

    def _score(
        self, items: list[Item], profile: WeatherProfile, occ: Occasion,
        temperature: int, raw_occasion: str,
    ) -> int:
        rule = BAND_RULES[profile.band]
        score = 100
        facts = [(item, self._facts(item)) for item in items]
        for item, fact in facts:
            if not item.minTemperature <= temperature <= item.maxTemperature:
                score -= 35
            if raw_occasion and _normalize(item.dressCode) not in {
                _normalize(raw_occasion), "any", "casual", "повседневный", occ.value, "",
            }:
                score -= 5
            if item.part == ItemPart.SHOES:
                score += 4
            elif item.part == ItemPart.ACCESSORY:
                score += 1
            if self._isOuterwear(item) and should_suggest_outerwear(profile):
                score += 8
            if self._isScarf(item) and should_suggest_scarf(profile):
                score += 3
            if should_suggest_sun(profile) and fact.key in {"sunglasses", "cap"}:
                score += 4
            if occ in {Occasion.DATE, Occasion.PARTY} and item.part == ItemPart.ACCESSORY:
                score += 3
            if occ == Occasion.TRAVEL and fact.key in {"sneakers", "bag"}:
                score += 3
            if occ == Occasion.OUTDOOR and fact.key in {"boots", "winter-boots", "sneakers"}:
                score += 4
            if fact.key in BAND_PREFERRED[profile.band]:
                score += PREFERRED_BONUS
            if occ in {Occasion.WORK, Occasion.FORMAL} and item.part != ItemPart.ACCESSORY \
                    and fact.formality >= 3:
                score += WORK_FORMAL_BONUS
        if profile.precipitation >= 0.2:
            if any(fact.waterproof for _, fact in facts):
                score += 18
            if any(fact.key in {"boots", "winter-boots"} for _, fact in facts):
                score += 6
            if any(fact.key == "umbrella" for _, fact in facts):
                score += 5
        warmth = sum(f.warmth for _, f in facts)
        target = (rule.comfort_min + min(rule.max, rule.comfort_min + 6)) / 2
        score -= int(abs(warmth - target))
        accents = {f.color for _, f in facts if not f.neutral}
        score -= 12 * max(0, len(accents) - 1)
        return max(score, 1)

    # ---------------------------------------------------------------- explain

    def explain(self, items: list[Item], weather: WeatherData, occasion: str, score: int) -> dict:
        profile = profile_from_weather(weather)
        occ = normalize_occasion(occasion)
        rule = BAND_RULES[profile.band]
        warmth = sum(self._facts(item).warmth for item in items)
        comfortable = self._weatherReason(items, profile, occ, True).compatible
        rules = [
            f"погода: {profile.feels_like}°C ощущается, диапазон {profile.band.value} ({rule.label})",
            f"правило диапазона: верх — {rule.top}; низ — {rule.bottom}; "
            f"обувь — {rule.shoes}; аксессуары — {rule.accessories}",
            f"повод: {occ.value}",
            f"условия: {profile.conditions}, ветер {profile.wind:.0f} км/ч, "
            f"осадки {profile.precipitation} мм, UV {profile.uv}",
            f"теплота набора {warmth} (допустимо {rule.absolute_min}–{rule.max}, "
            f"комфортно от {rule.comfort_min})",
        ]
        if should_suggest_outerwear(profile):
            rules.append("нужен слой верхней одежды")
        if should_suggest_scarf(profile):
            rules.append("рекомендован шарф")
        if profile.precipitation >= 0.2:
            rules.append("нужна защита от осадков")
        if should_suggest_sun(profile):
            rules.append("нужна солнцезащита")
        if not comfortable:
            rules.append("⚠ набор допустим, но не идеален: в гардеробе не хватило более подходящих вещей")
        return {
            "place": profile.place,
            "date": profile.date.isoformat(),
            "temperature": profile.temperature,
            "feelsLike": profile.feels_like,
            "band": profile.band.value,
            "wind": profile.wind,
            "humidity": profile.humidity,
            "precipitation": profile.precipitation,
            "uv": profile.uv,
            "conditions": profile.conditions,
            "occasion": occ.value,
            "source": profile.source,
            "score": score,
            "warmth": {
                "total": warmth, "min": rule.comfort_min, "max": rule.max,
                "absoluteMin": rule.absolute_min,
            },
            "comfortable": comfortable,
            "items": [f"{item.color} {item.type}" for item in items],
            "appliedRules": rules,
        }

    # --------------------------------------------------------------- generate

    def generateVariants(
        self, items: list[Item], weather: WeatherData, occasion: str = "everyday",
        preferences: Preferences | None = None,
        season: Season | None = None,
    ) -> list[Outfit]:
        profile = profile_from_weather(weather)
        occ = normalize_occasion(occasion)
        season = season or season_for(weather.date, weather.latitude)
        candidates = [
            item for item in items
            if item.isAvailable()
            and item.minTemperature <= weather.temperature <= item.maxTemperature
            and (not item.seasons or season in item.seasons)
            and self._itemFitsOccasion(item, occ)
            and not self._itemConflictsWeather(item, profile)
        ]

        def pool(selected: list[Item], limit: int) -> list[Item]:
            ranked = sorted(
                selected,
                key=lambda item: (-self._preferenceScore([item], preferences), item.id or 0),
            )
            return ranked[:limit]

        tops = pool([
            item for item in candidates
            if item.part == ItemPart.TOP and not self._isOnePiece(item)
            and not self._isOuterwear(item)
        ], 6)
        bottoms = pool([
            item for item in candidates
            if item.part == ItemPart.BOTTOM and not self._isOnePiece(item)
        ], 6)
        dresses = pool([item for item in candidates if self._isOnePiece(item)], 4)
        shoes = pool([item for item in candidates if item.part == ItemPart.SHOES], 3)
        outerwear_all = pool([item for item in candidates if self._isOuterwear(item)], 3)
        outerwear = outerwear_all if should_suggest_outerwear(profile) else []
        accessory_groups: dict[str, list[Item]] = {}
        for item in candidates:
            if item.part != ItemPart.ACCESSORY:
                continue
            if self._isScarf(item) and not should_suggest_scarf(profile):
                continue
            category = accessory_category_for_type(item.type)
            if category not in accessory_groups and len(accessory_groups) == 3:
                continue
            accessory_groups.setdefault(category, []).append(item)
        accessory_choices = [[None, *group[:2]] for group in accessory_groups.values()]
        accessory_selections = self._accessorySelections(accessory_choices)

        cores: list[tuple[Item, ...]] = [(dress,) for dress in dresses]
        cores.extend(product(tops, bottoms))

        variants: list[Outfit] = []
        seen: set[frozenset[int]] = set()
        for strict in (True, False):
            if len(variants) >= self.maxVariants:
                break
            scored = self._search(
                cores, shoes, outerwear, accessory_selections, profile, occ, weather,
                occasion, preferences, strict,
            )
            scored = [entry for entry in scored if frozenset(map(id, entry[1])) not in seen]
            for score, matched in self._diversify(scored, self.maxVariants - len(variants)):
                seen.add(frozenset(map(id, matched)))
                outfit = Outfit(
                    date=weather.date, place=weather.place, occasion=occasion,
                    items=list(matched),
                    debug=self.explain(list(matched), weather, occasion, score),
                )
                variants.append(outfit)
        return variants

    def _search(
        self, cores, shoes, outerwear, accessory_selections, profile, occ, weather,
        occasion, preferences, strict,
    ) -> list[tuple[int, tuple[Item, ...]]]:
        layers = [*outerwear] if (strict and outerwear) else [None, *outerwear]
        scored: list[tuple[int, tuple[Item, ...]]] = []
        for core in cores:
            for shoe in shoes:
                base = (*core, shoe)
                if not self.check(list(base)).compatible:
                    continue
                for layer in layers:
                    for selection in accessory_selections:
                        extras = tuple(item for item in (layer, *selection) if item is not None)
                        combo = (*base, *extras)
                        listed = list(combo)
                        if not self.check(listed).compatible:
                            continue
                        if not self._weatherReason(listed, profile, occ, strict).compatible:
                            continue
                        score = self._score(
                            listed, profile, occ, weather.temperature, occasion
                        ) + self._preferenceScore(listed, preferences)
                        scored.append((score, combo))
        scored.sort(key=lambda entry: (-entry[0], tuple(item.id or 0 for item in entry[1])))
        return scored

    @staticmethod
    def _diversify(
        scored: list[tuple[int, tuple[Item, ...]]], limit: int,
    ) -> list[tuple[int, tuple[Item, ...]]]:
        """Сначала лучшие образы с разной основой (верх+низ), потом — остальные."""
        picked: list[tuple[int, tuple[Item, ...]]] = []
        picked_ids: set[int] = set()
        used_cores: set[tuple[int, ...]] = set()
        for position, entry in enumerate(scored):
            core = tuple(
                id(item) for item in entry[1]
                if item.part in (ItemPart.TOP, ItemPart.BOTTOM, ItemPart.ONE_PIECE)
                and not CompatibilityRule._isOuterwear(item)
            )
            if core in used_cores:
                continue
            used_cores.add(core)
            picked.append(entry)
            picked_ids.add(position)
            if len(picked) == limit:
                return picked
        for position, entry in enumerate(scored):
            if position not in picked_ids:
                picked.append(entry)
                if len(picked) == limit:
                    break
        return picked

    # ------------------------------------------------------- item-level rules

    def _itemFitsOccasion(self, item: Item, occasion: Occasion) -> bool:
        fact = self._facts(item)
        if fact.key in OCCASION_FORBIDDEN_KEYS.get(occasion, frozenset()):
            return False
        text = _normalize(f"{item.type} {item.dressCode} {item.style}")
        accessory = item.part == ItemPart.ACCESSORY
        minimum = OCCASION_MIN_FORMALITY.get(occasion)
        if minimum and not accessory and fact.formality < minimum:
            return False
        if occasion == Occasion.FORMAL and "футболк" in text and "принт" in text:
            return False
        if occasion in {Occasion.FORMAL, Occasion.WORK, Occasion.DATE, Occasion.PARTY}:
            if fact.sporty and not accessory and "sport" in _normalize(item.dressCode + item.style) \
                    or fact.sporty and not accessory and "спорт" in _normalize(item.dressCode + item.style):
                return False
        if occasion == Occasion.SPORT and not accessory:
            if fact.key in {"dress-shoes", "loafers", "blazer", "coat", "shirt", "skirt", "dress",
                            "jumpsuit", "cardigan", "jeans"}:
                return False
            if item.part == ItemPart.SHOES and fact.key != "sneakers":
                return False
            if fact.key not in SPORT_NEUTRAL_KEYS and not fact.sporty:
                return False
        return True

    def _itemConflictsWeather(self, item: Item, profile: WeatherProfile) -> bool:
        fact = self._facts(item)
        if fact.key in BAND_RULES[profile.band].forbidden:
            return True
        if profile.precipitation >= 0.5 and fact.key == "sandals":
            return True
        # Пуховик в верхней части диапазона 5–12 °C — перебор: берём куртку или пальто.
        if profile.band == TemperatureBand.CHILLY and profile.feels_like >= 9 \
                and fact.key == "down-coat":
            return True
        return False

    @staticmethod
    def _preferenceScore(items: list[Item], preferences: Preferences | None) -> int:
        if preferences is None:
            return 0
        colors = {
            CompatibilityRule._canonicalColor(value)
            for value in preferences.colors.split(",") if value.strip()
        }
        styles = {value.strip().casefold() for value in preferences.style.split(",") if value.strip()}
        silhouettes = {
            value.strip().casefold()
            for value in preferences.bodyFeatures.split(",") if value.strip()
        }
        return sum(
            (12 if CompatibilityRule._canonicalColor(item.color) in colors else 0)
            + (10 if item.style.casefold() in styles else 0)
            + (5 if item.silhouette.casefold() in silhouettes else 0)
            for item in items
        )

    @classmethod
    def _isOnePiece(cls, item: Item) -> bool:
        return item.part == ItemPart.ONE_PIECE or item.type.casefold() in cls._dresses

    @staticmethod
    def _isOuterwear(item: Item) -> bool:
        return (
            item.part == ItemPart.OUTERWEAR
            or expected_part_for_type(item.type) == ItemPart.OUTERWEAR
        )

    @classmethod
    def _isScarf(cls, item: Item) -> bool:
        normalized = item.type.casefold()
        return any(marker in normalized for marker in cls._scarves)

    @staticmethod
    def _accessorySelections(choices: list[list[Item | None]]) -> list[tuple[Item | None, ...]]:
        return list(product(*choices)) if choices else [()]

    @staticmethod
    def _shouldSuggestOuterwear(weather: WeatherData) -> bool:
        return should_suggest_outerwear(profile_from_weather(weather))

    @staticmethod
    def _shouldSuggestScarf(weather: WeatherData) -> bool:
        return should_suggest_scarf(profile_from_weather(weather))

    def explainEmpty(
        self,
        items: list[Item],
        weather: WeatherData,
        occasion: str = "everyday",
        preferences: Preferences | None = None,
        season: Season | None = None,
    ) -> str:
        """Человеко-понятное объяснение, почему ни один образ не собрался.

        Возвращает фразу для пользователя: что не так, где это исправить,
        что именно поменять. Учитывает:
        * верх+низ+обувь ИЛИ платье/комбинезон+обувь — оба варианта полного образа;
        * вещи в стирке — подсказываем «заберите из стирки», а не «добавьте вещь»;
        * разницу стилей — указываем конкретную вещь, которую нужно поправить.
        """
        profile = profile_from_weather(weather)
        occ = normalize_occasion(occasion)
        season = season or season_for(weather.date, weather.latitude)

        # 1) Доступные вещи вообще есть?
        raw_candidates = [item for item in items if item.isAvailable()]
        in_laundry = [i for i in items if i.inLaundry and not i.deleted]

        if not raw_candidates:
            if in_laundry:
                names = ", ".join(f"«{i.type}»" for i in in_laundry[:3])
                return (
                    f"Все доступные вещи в стирке ({names}). "
                    "Заберите хотя бы часть из стирки — тогда получится собрать образ."
                )
            return (
                "В гардеробе нет доступных вещей. Добавьте вещи на странице «Гардероб» — "
                "или проверьте, не удалены ли они."
            )

        # 2) Подходят по погоде и сезону?
        season_temp_candidates = [
            item for item in raw_candidates
            if item.minTemperature <= weather.temperature <= item.maxTemperature
            and (not item.seasons or season in item.seasons)
        ]
        if not season_temp_candidates:
            return (
                f"Ни одна вещь не подходит под погоду сегодня ({weather.temperature} °C). "
                "Откройте «Гардероб», выберите вещь и расширьте диапазон температур "
                "или добавьте её в текущий сезон."
            )

        # 3) Подходят по поводу?
        occasion_candidates = [
            item for item in season_temp_candidates if self._itemFitsOccasion(item, occ)
        ]
        if not occasion_candidates:
            return (
                f"Для повода «{occ.value}» нет подходящих вещей. Попробуйте другой повод "
                "или добавьте в «Гардероб» вещи под этот случай."
            )

        # 4) Не противоречат погоде?
        weather_candidates = [
            item for item in occasion_candidates
            if not self._itemConflictsWeather(item, profile)
        ]
        if not weather_candidates:
            return (
                "Все подходящие вещи не подходят по погоде (например, сандалии в холод "
                "или пуховик в тепло). Добавьте вещи, соответствующие сегодняшней погоде."
            )

        # 4.5) Не хватает чего-то критичного И оно в стирке?
        parts_avail = Counter(item.part for item in weather_candidates)
        has_top_a = parts_avail.get(ItemPart.TOP, 0) > 0
        has_bottom_a = parts_avail.get(ItemPart.BOTTOM, 0) > 0
        has_shoes_a = parts_avail.get(ItemPart.SHOES, 0) > 0
        has_one_piece_a = any(self._isOnePiece(i) for i in weather_candidates)

        if in_laundry:
            laundry_parts = Counter(i.part for i in in_laundry)
            need_shoes_laundry = not has_shoes_a and laundry_parts.get(ItemPart.SHOES, 0) > 0
            need_bottom_laundry = (
                not has_one_piece_a and not has_bottom_a
                and laundry_parts.get(ItemPart.BOTTOM, 0) > 0
            )
            need_top_laundry = (
                not has_one_piece_a and not has_top_a
                and laundry_parts.get(ItemPart.TOP, 0) > 0
            )
            need_one_piece_laundry = (
                not has_one_piece_a
                and not (has_top_a and has_bottom_a)
                and laundry_parts.get(ItemPart.ONE_PIECE, 0) > 0
            )
            if need_shoes_laundry or need_bottom_laundry or need_top_laundry \
                    or need_one_piece_laundry:
                names = ", ".join(f"«{i.type}»" for i in in_laundry[:3])
                return (
                    f"В стирке {names}. Заберите их из стирки — тогда получится собрать образ."
                )

        # 5) Хватает ли слагаемых. Полный образ — это
        #    (верх + низ + обувь) ИЛИ (платье/комбинезон + обувь).
        if not has_shoes_a:
            return (
                "В гардеробе нет подходящей обуви под этот повод и погоду. "
                "Добавьте обувь на странице «Гардероб»."
            )

        if not has_one_piece_a and not (has_top_a and has_bottom_a):
            missing: list[str] = []
            if not has_top_a:
                missing.append("верх")
            if not has_bottom_a:
                missing.append("низ")

            any_one_piece_ever = any(self._isOnePiece(i) for i in raw_candidates)
            if not any_one_piece_ever and missing:
                return (
                    f"Для образа не хватает: {', '.join(missing)}. "
                    "Откройте «Гардероб» и добавьте эту вещь. "
                    "Либо добавьте платье или комбинезон — тогда верх и низ "
                    "не понадобятся."
                )
            if missing:
                return (
                    f"Для образа не хватает: {', '.join(missing)}. "
                    "Откройте «Гардероб» и добавьте эту вещь."
                )

        # 6) Все слагаемые есть. Перебираем комбинации.
        tops = [
            i for i in weather_candidates
            if i.part == ItemPart.TOP and not self._isOuterwear(i) and not self._isOnePiece(i)
        ][:6]
        bottoms = [
            i for i in weather_candidates
            if i.part == ItemPart.BOTTOM and not self._isOnePiece(i)
        ][:6]
        shoes = [i for i in weather_candidates if i.part == ItemPart.SHOES][:3]
        outerwear = [i for i in weather_candidates if self._isOuterwear(i)][:3]
        dresses = [i for i in weather_candidates if self._isOnePiece(i)][:4]

        issues: list[str] = []
        formal_issue_items: list[Item] = []

        cores: list[tuple[Item, ...]] = [(d,) for d in dresses]
        cores.extend(product(tops, bottoms))

        for core in cores:
            for shoe in shoes:
                base = (*core, shoe)
                structural = self.check(list(base))
                if not structural.compatible:
                    issues.append("color")
                    continue

                layers = [None, *outerwear] if should_suggest_outerwear(profile) else [None]
                for layer in layers:
                    combo = (*base, layer) if layer is not None else base
                    combo_list = list(combo)
                    facts = [(i, self._facts(i)) for i in combo_list]

                    formalities = [
                        f.formality for i, f in facts if i.part != ItemPart.ACCESSORY
                    ]
                    if formalities and max(formalities) - min(formalities) > 2:
                        formal_issue_items = [
                            i for i, f in facts
                            if f.formality == min(formalities) and i.part != ItemPart.ACCESSORY
                        ]
                        issues.append("style")
                        continue

                    total_warmth = sum(f.warmth for _, f in facts)
                    if total_warmth < BAND_RULES[profile.band].absolute_min:
                        issues.append("cold")
                        continue
                    if total_warmth > BAND_RULES[profile.band].max:
                        issues.append("warm")
                        continue

                    wc = self._weatherReason(combo_list, profile, occ, strict=False)
                    if not wc.compatible:
                        if "формальност" in wc.reason:
                            issues.append("style")
                        elif "теплота" in wc.reason and "нужно не меньше" in wc.reason:
                            issues.append("cold")
                        elif "теплота" in wc.reason and "не больше" in wc.reason:
                            issues.append("warm")
                        elif "акцент" in wc.reason or "цвет" in wc.reason:
                            issues.append("color")
                        elif "паттерн" in wc.reason:
                            issues.append("pattern")
                        elif "материал" in wc.reason:
                            issues.append("material")
                        else:
                            issues.append("other")

        if not issues:
            return "Не удалось подобрать образ по неизвестной причине."

        most_common, _ = Counter(issues).most_common(1)[0]

        if most_common == "style":
            names = ", ".join(f"«{item.type}»" for item in formal_issue_items[:2]) \
                if formal_issue_items else "некоторые вещи"
            return (
                f"Не удалось собрать образ: вещи слишком разные по стилю — "
                f"спортивные и нарядные вместе. Проверьте {names} в «Гардеробе» и "
                "измените у них дресс-код на «Casual»."
            )

        if most_common == "cold":
            return (
                f"На {weather.temperature} °C вашего набора вещей не хватает по теплу. "
                "Добавьте в «Гардероб» более тёплую вещь — свитер из шерсти, куртку, "
                "пальто или утеплённые штаны."
            )

        if most_common == "warm":
            return (
                f"Для {weather.temperature} °C вещи слишком тёплые. "
                "Уберите верхнюю одежду или замените свитер/пальто на что-то полегче."
            )

        if most_common == "color":
            return (
                "Не получается собрать образ: в нём слишком много ярких цветов. "
                "Оставьте один акцентный цвет, остальные выберите нейтральными "
                "(чёрный, белый, серый, бежевый)."
            )

        if most_common == "pattern":
            return (
                "В образе больше одного крупного принта или узора. "
                "Оставьте один — остальные вещи сделайте однотонными."
            )

        if most_common == "material":
            return (
                "Не получается сочетать зимние и летние материалы в одном образе. "
                "Проверьте материалы вещей — например, не смешивайте шерсть и лён."
            )

        return (
            "Не удалось подобрать образ. Попробуйте изменить дату, место или повод "
            "либо добавить больше вещей в «Гардероб»."
        )

    @staticmethod
    def _seasonFor(day: date, latitude: float | None = None) -> Season:
        return season_for(day, latitude)

    @classmethod
    @lru_cache(maxsize=1024)
    def _canonicalColor(cls, value: str) -> str:
        normalized = (value or "").strip().casefold()
        for canonical, aliases in cls.colorAliases.items():
            if normalized in aliases:
                return canonical
        return normalized
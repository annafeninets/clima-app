import { request, photoUrl } from "../core/api.js";
import { state, PARTS, SEASONS, SEASON_LABELS } from "../core/state.js";
import { escapeHTML, fileAsDataUrl, icon, itemCountLabel, showToast } from "../ui/helpers.js";
import { emptyState, heading, shell } from "../ui/layout.js";

const ITEM_SUGGESTIONS = {
  type: [
    "Футболка", "Поло", "Лонгслив", "Майка", "Топ", "Рубашка", "Блузка", "Туника",
    "Корсет", "Боди", "Свитер", "Джемпер", "Пуловер", "Водолазка", "Кардиган",
    "Свитшот", "Толстовка", "Худи", "Жилет", "Пиджак", "Блейзер", "Куртка",
    "Кожаная куртка", "Джинсовая куртка", "Бомбер", "Ветровка", "Анорак", "Парка",
    "Пуховик", "Пальто", "Тренч", "Плащ", "Дублёнка", "Шуба", "Платье", "Сарафан",
    "Юбка", "Брюки", "Классические брюки", "Джинсы", "Шорты", "Бермуды", "Капри",
    "Леггинсы", "Спортивные брюки", "Комбинезон", "Кроссовки", "Кеды", "Ботинки",
    "Ботильоны", "Сапоги", "Туфли", "Лоферы", "Мокасины", "Балетки", "Сандалии",
    "Сандалии на каблуке", "Босоножки", "Шлёпанцы", "Мюли", "Угги", "Шарф", "Шапка",
    "Перчатки", "Носки", "Колготки", "Ремень", "Сумка"
  ],
  color: [
    "Белый", "Молочный", "Чёрный", "Серый", "Светло-серый", "Тёмно-серый", "Бежевый",
    "Песочный", "Коричневый", "Шоколадный", "Синий", "Тёмно-синий", "Голубой",
    "Бирюзовый", "Зелёный", "Оливковый", "Хаки", "Красный", "Бордовый", "Розовый",
    "Пудровый", "Жёлтый", "Горчичный", "Оранжевый", "Фиолетовый", "Сиреневый",
    "Золотой", "Серебряный", "Разноцветный"
  ],
  dressCode: [
    "casual", "повседневный", "business", "деловой", "sport", "спортивный",
    "evening", "вечерний", "formal", "официальный", "smart casual", "any", "любой"
  ],
  style: [
    "Классический", "Casual", "Спортивный", "Минимализм", "Романтический", "Деловой",
    "Уличный", "Бохо", "Базовый", "Повседневный", "Элегантный", "Офисный", "Preppy",
    "Гранж", "Винтажный", "Ретро", "Рок", "Авангардный", "Скандинавский", "Тихая роскошь"
  ],
  material: [
    "Хлопок", "Лён", "Шерсть", "Мериносовая шерсть", "Кашемир", "Шёлк", "Вискоза",
    "Полиэстер", "Нейлон", "Акрил", "Эластан", "Деним", "Кожа", "Экокожа", "Замша",
    "Трикотаж", "Флис", "Вельвет", "Велюр", "Атлас", "Сатин", "Шифон", "Жаккард",
    "Кружево", "Твид", "Бархат", "Мембранная ткань", "Пух", "Смесовая ткань"
  ],
  silhouette: [
    "Прямой", "Свободный", "Приталенный", "Oversize", "Облегающий", "Широкий",
    "А-силуэт", "Relaxed", "Полуприлегающий", "Оверсайз", "Слим", "Skinny", "Slim fit",
    "Regular fit", "Свободный крой", "Прямой крой", "Зауженный", "Расклешённый",
    "Клёш", "Палаццо", "Карго", "Бананы", "Мом", "Бойфренд", "Высокая посадка",
    "Средняя посадка", "Низкая посадка", "Карандаш", "Трапеция", "Солнце", "Плиссе",
    "Футляр", "Баллон", "Кокон", "Тюльпан", "Ампир", "Принцесса", "Миди", "Макси",
    "Мини", "Укороченный", "Удлинённый", "Двубортный", "Однобортный", "На запах",
    "Асимметричный", "Многослойный", "Структурный"
  ]
};

const ITEM_TEXT_FIELDS = [
  ["type", "Тип вещи", "Например, футболка"],
  ["color", "Цвет", "Например, белый"],
  ["dressCode", "Повод / дресс-код", "Например, повседневный"],
  ["style", "Стиль", "Например, классический"],
  ["material", "Материал", "Например, хлопок"],
  ["silhouette", "Силуэт", "Например, прямой"]
];

const TOP_TYPE_MARKERS = [
  "футболк", "поло", "лонгслив", "майк", "топ", "рубаш", "блуз", "туник", "корсет",
  "боди", "свитер", "худи", "кардиган", "куртк", "пальто", "плащ", "пиджак",
  "жилет", "свитшот", "толстовк", "жакет", "блейзер", "джемпер", "пуловер", "парка",
  "ветровк", "анорак", "пухов", "тренч", "дубл", "шуб", "водолазк", "бомбер",
  "футбол", "blouse", "sweater", "hoodie", "jacket", "coat"
];
const BOTTOM_TYPE_MARKERS = [
  "джинс", "брюк", "штан", "юбк", "шорт", "бермуд", "леггинс", "лосин", "капри",
  "кроссов", "кед", "ботин", "ботильон", "сапог", "туфл", "лофер", "мокасин",
  "балет", "сандал", "босонож", "шлеп", "мюл", "угг", "jean", "trouser", "pants",
  "skirt", "shorts", "legging", "shoe", "boot"
];
const FOOTWEAR_TYPE_MARKERS = [
  "кроссов", "кед", "ботин", "ботильон", "сапог", "туфл", "лофер", "мокасин",
  "балет", "сандал", "босонож", "шлеп", "мюл", "угг", "shoe", "boot"
];
const SILHOUETTES_BY_CATEGORY = {
  upper: [
    "Прямой", "Свободный", "Приталенный", "Oversize", "Облегающий", "Relaxed",
    "Широкий", "Оверсайз", "Полуприлегающий", "Слим", "Slim fit", "Regular fit",
    "Свободный крой", "Прямой крой", "Укороченный", "Удлинённый", "Структурный",
    "На запах", "Асимметричный"
  ],
  lower: [
    "Прямой", "Свободный", "Широкий", "Облегающий", "Relaxed", "Skinny", "Slim fit",
    "Regular fit", "Зауженный", "Расклешённый", "Клёш", "Палаццо", "Карго", "Бананы",
    "Мом", "Бойфренд", "Высокая посадка", "Средняя посадка", "Низкая посадка",
    "Укороченный", "Удлинённый", "Карандаш", "Трапеция", "Плиссе"
  ],
  onePiece: [
    "Прямой", "Свободный", "Приталенный", "Облегающий", "А-силуэт", "Полуприлегающий",
    "Карандаш", "Трапеция", "Солнце", "Плиссе", "Футляр", "Баллон", "Кокон", "Тюльпан",
    "Ампир", "Принцесса", "Миди", "Макси", "Мини", "На запах", "Асимметричный"
  ],
  footwear: [
    "Кроссовки", "Кеды", "Ботинки", "Ботильоны", "Сапоги", "Туфли", "Лоферы",
    "Балетки", "Сандалии", "На каблуке", "На платформе", "На плоской подошве",
    "Высокое голенище", "Низкое голенище", "Округлый нос", "Острый нос",
    "Квадратный нос", "Массивная подошва", "Минималистичные"
  ],
  bag: [
    "Тоут", "Шоппер", "Кросс-боди", "Клатч", "Сэтчел", "Хобо", "Сумка-ведро",
    "Рюкзак", "Мини-сумка", "Структурная", "Мягкая форма", "Прямоугольная",
    "Круглая", "Полумесяц", "Вытянутая", "Компактная", "Объёмная"
  ],
  scarf: [
    "Длинный", "Короткий", "Широкий", "Узкий", "Треугольный", "Квадратный",
    "Палантин", "Снуд", "На запах", "Объёмный", "Лёгкий", "Плотный"
  ],
  accessory: [
    "Бини", "Бейсболка", "Панама", "Берет", "Кепка", "Широкополая",
    "Длинные", "Короткие", "Высокие", "Низкие", "Широкий", "Узкий",
    "Классический", "Компактный"
  ]
};
const CONTEXT_OPTIONS = {
  dressCode: {
    default: ITEM_SUGGESTIONS.dressCode,
    accessory: ["casual", "повседневный", "business", "деловой", "evening", "вечерний", "formal", "официальный", "any", "любой"],
    bag: ["casual", "повседневный", "business", "деловой", "evening", "вечерний", "formal", "официальный", "smart casual", "any", "любой"],
    footwear: ["casual", "повседневный", "business", "деловой", "sport", "спортивный", "evening", "вечерний", "formal", "официальный", "any", "любой"]
  },
  style: {
    default: ITEM_SUGGESTIONS.style,
    accessory: ["Классический", "Casual", "Повседневный", "Деловой", "Элегантный", "Минимализм", "Уличный", "Винтажный", "Ретро", "Базовый"],
    bag: ["Классический", "Casual", "Повседневный", "Деловой", "Элегантный", "Минимализм", "Уличный", "Бохо", "Винтажный", "Базовый"],
    footwear: ["Классический", "Casual", "Повседневный", "Спортивный", "Деловой", "Элегантный", "Минимализм", "Уличный", "Гранж", "Базовый"]
  },
  material: {
    default: ITEM_SUGGESTIONS.material,
    accessory: ["Хлопок", "Шерсть", "Кашемир", "Шёлк", "Кожа", "Экокожа", "Замша", "Трикотаж", "Флис", "Вельвет", "Атлас", "Сатин", "Кружево", "Металл", "Пластик"],
    bag: ["Кожа", "Экокожа", "Замша", "Деним", "Нейлон", "Полиэстер", "Хлопок", "Канвас", "Солома", "Плетёный материал"],
    footwear: ["Кожа", "Экокожа", "Замша", "Нубук", "Текстиль", "Деним", "Нейлон", "Резина", "Полиуретан", "Мембранная ткань", "Шерсть"]
  }
};

function normalizeSuggestion(value) {
  return value.trim().toLocaleLowerCase("ru").replaceAll("ё", "е");
}

function typeCategory(type) {
  const normalized = normalizeSuggestion(type);
  if (["сумк", "рюкзак", "клатч", "кошелек", "кошелёк", "bag"].some((marker) => normalized.includes(marker))) return "bag";
  if (FOOTWEAR_TYPE_MARKERS.some((marker) => normalized.includes(marker))) return "footwear";
  if (["шарф", "scarf"].some((marker) => normalized.includes(marker))) return "scarf";
  if (["шапк", "перчат", "носк", "колгот", "ремн"].some((marker) => normalized.includes(marker))) return "accessory";
  if (["плать", "сарафан", "комбинезон"].some((marker) => normalized.includes(marker))) return "onePiece";
  if (["куртк", "пальто", "плащ", "блейзер", "джинсовая куртка"].some((marker) => normalized.includes(marker))) return "upper";
  if (BOTTOM_TYPE_MARKERS.some((marker) => normalized.includes(marker))) return "lower";
  if (TOP_TYPE_MARKERS.some((marker) => normalized.includes(marker))) return "upper";
  return "upper";
}

export function expectedPartForType(type) {
  const normalized = normalizeSuggestion(type);
  if (FOOTWEAR_TYPE_MARKERS.some((marker) => normalized.includes(marker))) return "SHOES";
  if (["шарф", "шапк", "перчат", "носк", "колгот", "ремн", "сумк", "рюкзак", "клатч", "кошелек", "кошелёк", "scarf", "bag"].some((marker) => normalized.includes(marker))) return "ACCESSORY";
  if (["плать", "сарафан", "комбинезон", "dress", "jumpsuit"].some((marker) => normalized.includes(marker))) return "ONE_PIECE";
  const isTop = TOP_TYPE_MARKERS.some((marker) => normalized.includes(marker));
  const isBottom = BOTTOM_TYPE_MARKERS.some((marker) => normalized.includes(marker));
  if (isTop && isBottom && normalized.includes("куртк") && normalized.includes("джинс")) return "TOP";
  if (isTop && isBottom) return "MIXED";
  if (isTop) return "TOP";
  if (isBottom) return "BOTTOM";
  return "";
}

export function isValidItemText(value) {
  return /\p{L}/u.test(value) && /^[\p{L}\p{M}\p{N}\s.,'’()/#%+\-]+$/u.test(value);
}

function itemOptions(name, type = "", part = "") {
  const category = typeCategory(type);
  if (name === "type" && part) {
    const matchesPart = (option) => expectedPartForType(option) === part ||
      (!expectedPartForType(option) && (part === "TOP" || part === "BOTTOM"));
    const filtered = [
      ...ITEM_SUGGESTIONS.type,
      ...state.wardrobe.map((wardrobeItem) => wardrobeItem.type)
    ].filter(matchesPart);
    return [...new Map(filtered.map((option) => [normalizeSuggestion(option), option])).values()];
  }
  const allowed = name === "silhouette"
    ? SILHOUETTES_BY_CATEGORY[category] || []
    : CONTEXT_OPTIONS[name]?.[category] || CONTEXT_OPTIONS[name]?.default || ITEM_SUGGESTIONS[name];
  const allowedSet = new Set(allowed.map(normalizeSuggestion));
  if (name === "silhouette" && !allowed.length) return [];
  return [...new Map([
    ...allowed,
    ...state.wardrobe
      .filter((wardrobeItem) => name === "type" || typeCategory(wardrobeItem.type) === category)
      .map((wardrobeItem) => wardrobeItem[name])
      .filter((value) => value && allowedSet.has(normalizeSuggestion(value)))
  ].map((option) => [normalizeSuggestion(option), option])).values()];
}

function isValidItemOption(value, options) {
  return isValidItemText(value) && options.some(
    (option) => normalizeSuggestion(option) === normalizeSuggestion(value)
  );
}

function itemTextFieldError(name, value, type, part) {
  const [, label] = ITEM_TEXT_FIELDS.find(([fieldName]) => fieldName === name);
  const options = itemOptions(name, type, part);
  if (name === "silhouette" && !options.length) return "";
  if (!value) return `Заполните поле «${label.toLocaleLowerCase("ru")}».`;
  if (value.length > 100) return `Поле «${label.toLocaleLowerCase("ru")}» не должно превышать 100 символов.`;
  if (!isValidItemOption(value, options)) {
    return `Выберите корректный вариант поля «${label.toLocaleLowerCase("ru")}» из списка.`;
  }
  return "";
}

function editDistance(left, right) {
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= right.length; column += 1) {
      current[column] = Math.min(
        current[column - 1] + 1,
        previous[column] + 1,
        previous[column - 1] + (left[row - 1] === right[column - 1] ? 0 : 1)
      );
    }
    previous = current;
  }
  return previous[right.length];
}

function suggestionMatches(value, query) {
  const candidate = normalizeSuggestion(value);
  if (candidate.startsWith(query)) return 0;
  if (candidate.includes(query)) return 1;
  let queryIndex = 0;
  for (const character of candidate) {
    if (character === query[queryIndex]) queryIndex += 1;
    if (queryIndex === query.length) return 2;
  }
  const firstWord = candidate.split(/\s+/)[0];
  return query.length >= 3 && editDistance(query, firstWord) <= Math.max(1, Math.floor(query.length / 4)) ? 3 : -1;
}

function attachAutocomplete(input, list, getCandidates) {
  let activeIndex = -1;
  const close = () => {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activeIndex = -1;
  };
  const render = (showAll = false) => {
    const query = normalizeSuggestion(input.value);
    const candidates = getCandidates();
    const matches = candidates
      .map((value) => ({ value, score: query ? suggestionMatches(value, query) : 0 }))
      .filter(({ score }) => score >= 0)
      .sort((left, right) => showAll && !query
        ? left.value.localeCompare(right.value, "ru")
        : left.score - right.score || left.value.localeCompare(right.value, "ru"))
      .slice(0, showAll && !query ? candidates.length : 7);
    if (!matches.length) {
      close();
      return;
    }
    activeIndex = -1;
    list.innerHTML = matches.map(({ value }, index) =>
      `<button class="autocomplete-option" type="button" role="option" id="${list.id}-option-${index}" aria-selected="false" data-suggestion="${escapeHTML(value)}">${escapeHTML(value)}</button>`
    ).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };
  const choose = (value) => {
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    close();
  };

  input.addEventListener("focus", () => render(true));
  input.addEventListener("input", () => render());
  input.addEventListener("blur", () => window.setTimeout(close, 120));
  input.addEventListener("keydown", (event) => {
    const options = [...list.querySelectorAll('[role="option"]')];
    if (event.key === "Escape") {
      close();
    } else if (options.length && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      activeIndex = (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options.forEach((option, index) => {
        option.setAttribute("aria-selected", String(index === activeIndex));
      });
      input.setAttribute("aria-activedescendant", options[activeIndex].id);
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      choose(options[activeIndex].dataset.suggestion);
    }
  });
  list.addEventListener("mousedown", (event) => event.preventDefault());
  list.addEventListener("click", (event) => {
    const option = event.target.closest("[data-suggestion]");
    if (option) choose(option.dataset.suggestion);
  });
}

async function itemCard(item) {
  const src = await photoUrl(item.photo);
  const photo = src
    ? `<img src="${escapeHTML(src)}" alt="${escapeHTML(`${item.color} ${item.type}`)}" />`
    : `<div class="photo-placeholder">${icon("image")}</div>`;
  const seasons = (item.seasons || []).map((season) => SEASON_LABELS[season] || season).join(" · ");
  return `<article class="card item-card"><div class="item-photo">${photo}<span class="badge item-badge ${item.inLaundry ? "muted" : ""}">${item.inLaundry ? "В стирке" : escapeHTML(PARTS[item.part] || "Вещь")}</span><button class="item-menu" title="Редактировать" data-action="edit-item" data-id="${item.id}">···</button></div><div class="item-content"><h3>${escapeHTML(item.type)}</h3><div class="item-color">${escapeHTML(item.color)}${item.material ? ` · ${escapeHTML(item.material)}` : ""}</div><div class="item-chips"><span class="chip">${escapeHTML(seasons || "Все сезоны")}</span><span class="chip">${escapeHTML(item.minTemperature)}°…${escapeHTML(item.maxTemperature)}°</span></div><div class="item-footer"><span>${escapeHTML(item.dressCode || "Повседневный")}</span><button class="text-link" data-action="laundry" data-id="${item.id}" data-value="${!item.inLaundry}">${item.inLaundry ? "Готова" : "В стирку"}</button></div></div></article>`;
}

export async function renderWardrobe() {
  const filtered = state.wardrobe.filter((item) => {
    const matchesFilter = state.filter === "ALL" || item.part === state.filter ||
      (state.filter === "CLEAN" && !item.inLaundry) || (state.filter === "LAUNDRY" && item.inLaundry);
    const text = `${item.type} ${item.color} ${item.material}`.toLocaleLowerCase("ru");
    return matchesFilter && text.includes(state.search.toLocaleLowerCase("ru"));
  });
  const cards = await Promise.all(filtered.map(itemCard));
  const action = `<button class="button secondary" data-action="compose-outfit">${icon("sparkle")}Собрать образ</button><button class="button" data-action="open-item">${icon("plus")}Добавить вещь</button>`;
  return shell(`${heading("Мой гардероб", `${itemCountLabel(state.wardrobe.length)} в вашей коллекции. Каждая вещь — часть будущего образа.`, action)}
    <div class="toolbar"><div class="search-field">${icon("search")}<input id="wardrobe-search" placeholder="Найти вещь..." value="${escapeHTML(state.search)}" /></div><div class="filter-pills">${[["ALL", "Все"], ...Object.entries(PARTS), ["CLEAN", "Чистые"], ["LAUNDRY", "В стирке"]].map(([value, label]) => `<button class="filter-pill ${state.filter === value ? "active" : ""}" data-filter="${value}">${label}</button>`).join("")}</div></div>
    ${cards.length ? `<div class="wardrobe-grid">${cards.join("")}</div>` : emptyState(state.wardrobe.length ? "Ничего не найдено" : "Ваш гардероб ждёт первую вещь", state.wardrobe.length ? "Попробуйте изменить поиск или фильтр." : "Добавьте фото любимой вещи и укажите её характеристики — Clima позаботится об остальном.", state.wardrobe.length ? "" : "Добавить вещь", state.wardrobe.length ? "" : "open-item")}`);
}

export function openItemForm(item = {}) {
  const isEdit = Boolean(item.id);
  const hasExistingPhoto = Boolean(item.photo);
  const checkedSeasons = item.seasons || [];
  const textFields = ITEM_TEXT_FIELDS.map(([name, label, placeholder]) => {
    const id = `item-${name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`;
    const value = item[name] || "";
    const options = itemOptions(name, item.type || "");
    return {
      name,
      label,
      markup: `<div class="field"><label for="${id}">${label}</label><div class="autocomplete"><input id="${id}" name="${name}" required maxlength="100" value="${escapeHTML(value)}" placeholder="${placeholder}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="${id}-suggestions" aria-describedby="${id}-error" /><div class="autocomplete-list" id="${id}-suggestions" role="listbox" hidden></div></div><small class="field-error" id="${id}-error" aria-live="polite"></small></div>`,
      options
    };
  });
  const textField = (name) => textFields.find((field) => field.name === name).markup;
  const preview = item.photo?.startsWith("data:")
    ? `<div class="field wide"><img src="${escapeHTML(item.photo)}" style="width:84px;height:84px;border-radius:12px;object-fit:cover" alt="Фото вещи" /></div>` : "";
  const form = `<form id="item-form" class="item-form" data-id="${item.id || ""}" data-has-photo="${hasExistingPhoto}" novalidate><div class="form-grid item-form-grid">
    <label class="file-drop wide" for="item-photo" tabindex="-1">${icon("image")}<span id="file-label">${isEdit ? "Заменить фото (необязательно)" : "Загрузить фото · обязательно, до 5 МБ"}</span><input id="item-photo" name="photo" type="file" accept="image/png,image/jpeg,image/gif,image/webp" /></label>
    ${preview}
    ${textField("type")}
    ${textField("color")}
    <div class="field"><label for="item-part">Часть образа</label><select id="item-part" name="part" required aria-describedby="item-part-error"><option value="" ${item.part ? "" : "selected"} disabled>Выберите часть образа</option>${Object.entries(PARTS).map(([value, label]) => `<option value="${value}" ${item.part === value ? "selected" : ""}>${label}</option>`).join("")}</select><small class="field-error" id="item-part-error" aria-live="polite"></small></div>
    ${textField("dressCode")}
    <div class="field wide"><span class="field-label">Сезоны</span><div class="season-options">${SEASONS.map((season) => `<label class="season-option"><input type="checkbox" name="seasons" value="${season}" ${checkedSeasons.includes(season) ? "checked" : ""} /><span>${SEASON_LABELS[season]}</span></label>`).join("")}</div></div>
    <div class="field"><label for="min-temp">От, °C</label><input id="min-temp" name="minTemperature" type="number" min="-50" max="50" step="1" required value="${item.minTemperature ?? ""}" placeholder="−50…50" /><small class="field-hint">Допустимо от −50 до 50 °C</small></div>
    <div class="field"><label for="max-temp">До, °C</label><input id="max-temp" name="maxTemperature" type="number" min="-50" max="50" step="1" required value="${item.maxTemperature ?? ""}" placeholder="−50…50" /><small class="field-hint">Допустимо от −50 до 50 °C</small></div>
    ${textField("style")}
    ${textField("material")}
    ${textField("silhouette")}
    ${isEdit ? `<div class="field"><label for="item-laundry">Стирка</label><select id="item-laundry" name="inLaundry"><option value="false" ${!item.inLaundry ? "selected" : ""}>Чистая</option><option value="true" ${item.inLaundry ? "selected" : ""}>В стирке</option></select></div>` : ""}
    </div><div class="form-errors" id="item-form-errors" role="alert" aria-live="polite"></div><div class="modal-footer"><button class="button secondary" type="button" data-action="close-modal">Отмена</button>${isEdit ? `<button class="button danger" type="button" data-action="delete-item" data-id="${item.id}">Удалить</button>` : ""}<button class="button" type="submit">${isEdit ? "Сохранить" : "Добавить в гардероб"}</button></div></form>`;
  const root = document.querySelector("#modal-root");
  root.innerHTML = `<div class="modal-backdrop" data-action="backdrop"><section class="modal" role="dialog" aria-modal="true"><header class="modal-header"><div><h2>${isEdit ? "Редактировать вещь" : "Новая вещь"}</h2><p class="page-subtitle">Добавьте фото и характеристики — они помогут подобрать образ.</p></div><button class="modal-close" data-action="close-modal" aria-label="Закрыть">${icon("close")}</button></header>${form}</section></div>`;
  const typeInput = root.querySelector("#item-type");
  const refreshTypeDependentFields = () => {
    for (const name of ["dressCode", "style", "material", "silhouette"]) {
      const input = root.querySelector(`#item-${name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`);
      const field = input.closest(".field");
      const list = root.querySelector(`#${input.id}-suggestions`);
      const options = itemOptions(name, typeInput.value, root.querySelector("#item-part").value);
      if (name === "silhouette") {
        const supported = options.length > 0;
        field.hidden = !supported;
        input.disabled = !supported;
        input.required = supported;
        if (!supported) {
          input.value = "";
          input.setAttribute("aria-invalid", "false");
          field.querySelector(".field-error").textContent = "";
        }
      } else if (input.value && !isValidItemOption(input.value, options)) {
        input.value = "";
        input.setAttribute("aria-invalid", "false");
        field.querySelector(".field-error").textContent = "";
      }
      if (list && !list.hidden) list.hidden = true;
    }
    const part = root.querySelector("#item-part");
    const expectedPart = expectedPartForType(typeInput.value);
    if (expectedPart) part.value = expectedPart;
    for (const { name } of textFields) {
      const input = root.querySelector(`#item-${name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`);
      if (input.getAttribute("aria-invalid") !== "true") continue;
      const message = itemTextFieldError(name, input.value.trim(), typeInput.value, part.value);
      input.setAttribute("aria-invalid", String(Boolean(message)));
      root.querySelector(`#${input.id}-error`).textContent = message;
    }
  };
  textFields.forEach(({ name }) => {
    const id = `item-${name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`;
    const input = root.querySelector(`#${id}`);
    input.addEventListener("input", () => {
      const message = itemTextFieldError(
        name, input.value.trim(), typeInput.value,
        root.querySelector("#item-part").value
      );
      input.setAttribute("aria-invalid", String(Boolean(message)));
      root.querySelector(`#${id}-error`).textContent = message;
    });
    attachAutocomplete(input, root.querySelector(`#${id}-suggestions`), () =>
      itemOptions(name, typeInput.value, root.querySelector("#item-part").value)
    );
  });
  typeInput.addEventListener("input", refreshTypeDependentFields);
  root.querySelector("#item-part").addEventListener("change", () => {
    if (!typeInput.value || !isValidItemOption(typeInput.value, itemOptions("type", "", root.querySelector("#item-part").value))) {
      typeInput.value = "";
    }
    refreshTypeDependentFields();
  });
  refreshTypeDependentFields();
  root.querySelector("#item-photo")?.addEventListener("change", () => {
    const errors = root.querySelector("#item-form-errors");
    if (errors) errors.textContent = "";
  });
  const itemForm = root.querySelector("#item-form");
  itemForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (itemForm.dataset.submitting === "true") return;
    itemForm.dataset.submitting = "true";
    const submitButton = itemForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.textContent = "Сохранение…";
    try {
      if (await saveItem(event)) window.dispatchEvent(new Event("clima:item-saved"));
    } catch (error) {
      showItemSaveError(itemForm, error);
    } finally {
      if (itemForm.isConnected) {
        delete itemForm.dataset.submitting;
        submitButton.disabled = false;
        submitButton.textContent = isEdit ? "Сохранить" : "Добавить в гардероб";
      }
    }
  });
}

function showItemSaveError(form, error) {
  const message = error.message || "Не удалось сохранить вещь.";
  const normalized = normalizeSuggestion(message);
  let target = null;
  if (normalized.includes("фото")) {
    target = form.querySelector(".file-drop");
    target?.classList.add("invalid");
  } else if (normalized.includes("сезон")) {
    target = form.querySelector(".season-options");
    target?.classList.add("invalid");
  } else if (normalized.includes("температур")) {
    target = form.querySelector(normalized.includes("максим") ? "#max-temp" : "#min-temp");
  } else if (normalized.includes("силуэт")) {
    target = form.elements.namedItem("silhouette");
  } else if (normalized.includes("цвет")) {
    target = form.elements.namedItem("color");
  } else if (normalized.includes("тип")) {
    target = form.elements.namedItem("type");
  } else {
    target = form.elements.namedItem("part");
  }
  if (target && target.matches("input, select")) {
    target.setAttribute("aria-invalid", "true");
    const errorElement = form.querySelector(`#${target.id}-error`) ||
      target.closest(".field")?.querySelector(".field-error");
    if (errorElement) errorElement.textContent = message;
  }
  if (normalized.includes("некорректные характеристики")) {
    form.querySelector("#item-form-errors").textContent =
      "Сервер не распознал выбранную часть образа. Обновите backend, чтобы применились категории обуви и аксессуаров.";
    form.elements.namedItem("part").setAttribute("aria-invalid", "true");
    form.querySelector("#item-part-error").textContent =
      "Сервер может не поддерживать выбранную категорию. Перезапустите или обновите backend.";
    return;
  }
  form.querySelector("#item-form-errors").textContent = message;
  target?.focus();
  target?.scrollIntoView({ block: "center", behavior: "smooth" });
}

export async function saveItem(event) {
  event.preventDefault();
  const form = event.currentTarget;
  form.querySelectorAll('[aria-invalid="true"]').forEach((field) => field.removeAttribute("aria-invalid"));
  form.querySelector(".season-options")?.classList.remove("invalid");
  form.querySelector(".file-drop")?.classList.remove("invalid");
  form.querySelectorAll(".field-error").forEach((message) => { message.textContent = ""; });
  const data = new FormData(form);
  const id = form.dataset.id;
  const file = data.get("photo");
  const errors = document.querySelector("#item-form-errors");
  const validTypes = ["image/png", "image/jpeg", "image/gif", "image/webp"];
  const fileSelected = file instanceof File && file.size > 0;
  const currentPhotoExists = form.dataset.hasPhoto === "true";
  const type = String(data.get("type") || "").trim();
  const color = String(data.get("color") || "").trim();
  const expectedPart = expectedPartForType(type);
  const rawMinimum = String(data.get("minTemperature") ?? "").trim();
  const rawMaximum = String(data.get("maxTemperature") ?? "").trim();
  const minimum = Number(rawMinimum);
  const maximum = Number(rawMaximum);
  const seasons = data.getAll("seasons");
  const textValues = Object.fromEntries(ITEM_TEXT_FIELDS.map(([name]) =>
    [name, String(data.get(name) ?? "").trim()]
  ));
  const invalidTextFields = ITEM_TEXT_FIELDS.flatMap(([name, label]) => {
    const value = textValues[name];
    const message = itemTextFieldError(
      name, value, type, String(data.get("part") || "")
    );
    return message ? [{ name, message }] : [];
  });
  ITEM_TEXT_FIELDS.forEach(([name]) => {
    const input = form.elements.namedItem(name);
    const error = form.querySelector(`#${input.id}-error`);
    const fieldError = invalidTextFields.find((invalid) => invalid.name === name);
    input.setAttribute("aria-invalid", String(Boolean(fieldError)));
    error.textContent = fieldError?.message || "";
  });
  if (invalidTextFields.length) {
    if (errors) errors.textContent = "Проверьте отмеченные поля: " +
      invalidTextFields.map(({ name }) =>
        ITEM_TEXT_FIELDS.find(([fieldName]) => fieldName === name)[1].toLocaleLowerCase("ru")
      ).join(", ") + ".";
    const invalidInput = form.elements.namedItem(invalidTextFields[0].name);
    invalidInput.focus();
    invalidInput.scrollIntoView({ block: "center", behavior: "smooth" });
    return false;
  }
  let validationError = null;

  if (!fileSelected && !currentPhotoExists) {
    validationError = { message: "Добавьте фото вещи — оно обязательно.", selector: ".file-drop" };
  } else if (fileSelected && !validTypes.includes(file.type)) {
    validationError = { message: "Поддерживаются фотографии PNG, JPEG, GIF и WebP.", selector: ".file-drop" };
  } else if (fileSelected && file.size > 5 * 1024 * 1024) {
    validationError = { message: "Размер фотографии не должен превышать 5 МБ.", selector: ".file-drop" };
  } else if (expectedPart === "MIXED") {
    validationError = { message: "В типе вещи указаны одновременно верх и низ. Укажите одну вещь в одном поле.", selector: '[name="type"]' };
  } else if (expectedPart && expectedPart !== data.get("part")) {
    const expectedPartLabel = PARTS[expectedPart] || "другой категории";
    validationError = { message: `Тип вещи «${type}» относится к категории «${expectedPartLabel.toLocaleLowerCase("ru")}». Измените часть образа или укажите другой тип вещи.`, selector: "#item-part" };
  } else if (!Object.hasOwn(PARTS, data.get("part"))) {
    validationError = { message: "Выберите корректную часть образа.", selector: "#item-part" };
  } else if (!seasons.length || seasons.some((season) => !SEASONS.includes(season))) {
    validationError = { message: "Выберите хотя бы один корректный сезон.", selector: '[name="seasons"]' };
  } else if (rawMinimum === "" || !Number.isSafeInteger(minimum)) {
    validationError = { message: "Укажите целую минимальную температуру.", selector: "#min-temp" };
  } else if (rawMaximum === "" || !Number.isSafeInteger(maximum)) {
    validationError = { message: "Укажите целую максимальную температуру.", selector: "#max-temp" };
  } else if (minimum < -50 || minimum > 50) {
    validationError = { message: "Минимальная температура должна быть от −50 до 50 °C.", selector: "#min-temp" };
  } else if (maximum < -50 || maximum > 50) {
    validationError = { message: "Максимальная температура должна быть от −50 до 50 °C.", selector: "#max-temp" };
  } else if (minimum > maximum) {
    validationError = { message: "Минимальная температура не может быть выше максимальной.", selector: "#min-temp" };
  }

  if (validationError) {
    if (errors) errors.textContent = validationError.message;
    const invalidField = form.querySelector(validationError.selector);
    if (validationError.selector === ".file-drop") {
      invalidField?.classList.add("invalid");
    } else if (validationError.selector === '[name="seasons"]') {
      form.querySelector(".season-options")?.classList.add("invalid");
      invalidField?.setAttribute("aria-invalid", "true");
    } else {
      invalidField?.setAttribute("aria-invalid", "true");
    }
    invalidField?.focus();
    invalidField?.scrollIntoView({ block: "center", behavior: "smooth" });
    return false;
  }

  try {
    let photo = "";
    if (fileSelected) photo = await fileAsDataUrl(file);
    const card = {
      type, color, part: data.get("part"), seasons,
      minTemperature: minimum, maxTemperature: maximum,
      dressCode: textValues.dressCode, style: textValues.style,
      material: textValues.material, silhouette: textValues.silhouette
    };
    if (!card.seasons.length) throw new Error("Выберите хотя бы один сезон");
    if (card.minTemperature > card.maxTemperature) throw new Error("Минимальная температура выше максимальной");
    if (id) {
      await request(`/wardrobe/items/${id}`, { method: "PUT", body: card });
      if (photo) await request(`/wardrobe/items/${id}/photo`, { method: "PUT", body: { photo } });
      await request(`/wardrobe/items/${id}/laundry`, { method: "PUT", body: { value: data.get("inLaundry") === "true" } });
    } else {
      const draft = await request("/wardrobe/items", { method: "POST", body: { photo } });
      await request("/wardrobe/items/draft", { method: "PUT", body: { ...card, photo: draft.photo } });
    }
    document.querySelector("#modal-root").innerHTML = "";
    showToast(id ? "Изменения сохранены" : "Вещь добавлена в гардероб");
    return true;
  } catch (error) {
    if (errors) errors.textContent = error.message || "Не удалось сохранить вещь.";
    return false;
  }
}

export async function changeLaundry(id, value) {
  await request(`/wardrobe/items/${id}/laundry`, { method: "PUT", body: { value } });
}

export async function deleteItem(id) {
  await request(`/wardrobe/items/${id}`, { method: "DELETE" });
}

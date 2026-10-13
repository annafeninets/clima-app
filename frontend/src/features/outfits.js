import { request } from "../core/api.js";
import { setPlace, state, PARTS } from "../core/state.js?v=20261012-01";
import { escapeHTML, humanDate, icon, itemCountLabel, showToast, today } from "../ui/helpers.js";
import { emptyState, heading, shell } from "../ui/layout.js";
import { OutfitCollage } from "./outfit-collage.js?v=20261012-07";

export const OCCASIONS = [
  { value: "everyday", title: "На каждый день" },
  { value: "work", title: "Работа" },
  { value: "casual", title: "Casual" },
  { value: "sport", title: "Спорт" },
  { value: "date", title: "Свидание" },
  { value: "formal", title: "Торжественный" },
  { value: "travel", title: "Путешествие" },
  { value: "party", title: "Вечеринка" },
  { value: "outdoor", title: "Прогулка / outdoor" }
];

function occasionLabel(value) {
  return OCCASIONS.find((item) => item.value === value)?.title || value || "";
}

/**
 * Нормализует строку для ключа дедупликации:
 * - приводит к нижнему регистру
 * - заменяет «ё» на «е»
 * - отбрасывает всё после слэша (например, «Платье / комбинезон» → «платье»)
 * - убирает лишние пробелы
 */
function normKey(str) {
  return String(str || "")
    .toLowerCase()
    .replaceAll("ё", "е")
    .replace(/\s*\/\s*.*$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Убирает дубликаты образов по СМЫСЛУ, а не по id.
 *
 * Два образа считаются одинаковыми, если у них совпадает набор вещей
 * по (part + type + color + material). Порядок не важен.
 */
function dedupeOutfits(outfits) {
  if (!Array.isArray(outfits)) return [];
  const seen = new Set();
  const unique = [];
  for (const outfit of outfits) {
    const items = Array.isArray(outfit?.items) ? outfit.items : [];
    const keys = items
      .map((item) => {
        const part = normKey(item?.part);
        const type = normKey(item?.type);
        const color = normKey(item?.color);
        const material = normKey(item?.material);
        if (type || color) {
          return `${part}::${type}::${color}::${material}`;
        }
        return `id::${item?.id ?? ""}`;
      })
      .sort();
    const key = keys.join("|") || `empty-${outfit?.id ?? Math.random()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(outfit);
  }
  return unique;
}

function debugPanel(outfit) {
  const debug = outfit.debug;
  if (!debug) return "";
  const rules = (debug.appliedRules || [])
    .map((rule) => `<li>${escapeHTML(rule)}</li>`)
    .join("");
  return `<details class="outfit-debug"><summary>Почему этот образ</summary>
    <p>Город: ${escapeHTML(debug.place || outfit.place || "")} · дата ${escapeHTML(debug.date || outfit.date || "")}</p>
    <p>Погода: ${escapeHTML(String(debug.feelsLike ?? debug.temperature ?? ""))}°C ощущается (${escapeHTML(debug.band || "")}), ${escapeHTML(debug.conditions || "")}</p>
    <p>Ветер ${escapeHTML(String(debug.wind ?? 0))} км/ч · осадки ${escapeHTML(String(debug.precipitation ?? 0))} мм · UV ${escapeHTML(String(debug.uv ?? 0))} · источник ${escapeHTML(debug.source || "")}</p>
    <p>Повод: ${escapeHTML(occasionLabel(debug.occasion || outfit.occasion))} · оценка ${escapeHTML(String(debug.score ?? ""))}</p>
    <ul>${rules}</ul>
  </details>`;
}

export async function outfitCard(outfit, favorite = null, allowSelect = true) {
  const items = outfit.items || [];
  const collage = await OutfitCollage(outfit);

  const isFavorite = Boolean(favorite);
  const favoriteButton = isFavorite
    ? `<button class="button small active" data-action="toggle-favorite" data-id="${outfit.id}" data-favorite-id="${favorite.id}" aria-pressed="true" aria-label="Убрать из избранного">${icon("heart")}Сохранён</button>`
    : `<button class="button secondary small" data-action="toggle-favorite" data-id="${outfit.id}" aria-pressed="false" aria-label="Сохранить в избранное">${icon("heart")}Сохранить</button>`;

  const isSelected = Boolean(outfit.selected);
  const selectButton = allowSelect
    ? (isSelected
        ? `<button class="button small active" data-action="toggle-select" data-id="${outfit.id}" data-selected="true" aria-pressed="true" aria-label="Снять отметку">${icon("check")}Надето</button>`
        : `<button class="button small" data-action="toggle-select" data-id="${outfit.id}" data-selected="false" aria-pressed="false" aria-label="Отметить как надетое">${icon("close")}Не надето</button>`)
    : "";

  const rating = outfit.selected && !outfit.rating
    ? `<div class="rating" aria-label="Оценить образ">${[1, 2, 3, 4, 5]
        .map((score) => `<button title="${score}" data-action="rate" data-id="${outfit.id}" data-score="${score}">${icon("star")}</button>`)
        .join("")}</div>`
    : outfit.rating
      ? `<span class="badge muted">Оценка ${outfit.rating}/5</span>`
      : "";

  const replacements = favorite
    ? (items || []).map((item) => {
        const choices = state.wardrobe.filter((candidate) =>
          candidate.part === item.part &&
          candidate.id !== item.id &&
          !candidate.inLaundry &&
          !candidate.deleted
        );
        if (!choices.length) return "";
        return `<div class="replace-row"><select aria-label="Заменить ${escapeHTML(item.type)}" id="replace-${favorite.id}-${item.id}"><option value="">Заменить ${escapeHTML(item.type)}</option>${choices
          .map((choice) => `<option value="${choice.id}">${escapeHTML(choice.color)} ${escapeHTML(choice.type)}</option>`)
          .join("")}</select><button class="button secondary small" data-action="replace-item" data-favorite="${favorite.id}" data-item="${item.id}">Ок</button></div>`;
      }).join("")
    : "";

  return `<article class="card outfit-card">
    ${collage}
    <div class="outfit-body">
      <div class="outfit-title"><h3>Образ на ${escapeHTML(humanDate(outfit.date))}</h3>${outfit.selected ? '<span class="badge">Выбран</span>' : ""}</div>
      <div class="outfit-meta">${escapeHTML(outfit.place || "")}${outfit.occasion ? ` · ${escapeHTML(occasionLabel(outfit.occasion))}` : ""}</div>
      <div class="item-chips">${items.map((item) => `<span class="chip">${escapeHTML(item.color || "")} ${escapeHTML(item.type || "")}</span>`).join("")}</div>
      ${debugPanel(outfit)}
      <div class="outfit-actions">${selectButton}${favoriteButton}${rating}</div>
      ${replacements ? `<div>${replacements}</div>` : ""}
    </div>
  </article>`;
}

/* ==========================================================================
   HERO — «Дама с веером». В правом верхнем углу — компас с розовой стрелкой.
   ========================================================================== */
function hero() {
  return `
<section class="hero" aria-label="Clima — стиль по погоде">
  <div class="bg-photo" aria-hidden="true"></div>
  <div class="bg-overlay" aria-hidden="true"></div>
  <div class="bg-gradient" aria-hidden="true"></div>

  <div class="hero-badge">ГАРМОНИЯ С ПОГОДОЙ · Clima 2026</div>

  <div class="fan-circle" aria-hidden="true">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
    <!-- внешний круг -->
    <circle cx="12" cy="12" r="9"/>
    <!-- четыре луча компаса -->
    <path d="M12 4v3M12 17v3M4 12h3M17 12h3"/>
    <!-- ромбовидная стрелка — только контуром -->
    <path d="M12 8.5 14 12 12 15.5 10 12Z"/>
    <!-- центральная точка -->
    <circle cx="12" cy="12" r="0.6" fill="currentColor"/>
  </svg>
</div>

  <div class="hero-content-block">
    <h1>Хороший день <em>начинается</em> с образа</h1>
    <p>Персональные сочетания из вашего гардероба — с учётом погоды, повода и настроения.</p>
    <button class="hero-btn" type="button" data-page="plan">Смотреть образ →</button>
    <div class="hero-caption">Персональный стилист по подбору аутфита по погоде</div>
  </div>

  <div class="hero-signature" aria-hidden="true">Clima 2026</div>
</section>
  `;
}

export async function renderHome() {
  const available = state.wardrobe.filter((item) => !item.inLaundry && !item.deleted).length;
  const uniqueOutfits = dedupeOutfits(state.outfits);
  const cards = await Promise.all(uniqueOutfits.slice(0, 3).map((outfit) => outfitCard(outfit)));
  const content = `
    ${hero()}

    <div class="stats-row">
      <div class="card stat-card"><div class="stat-icon">${icon("hanger")}</div><div><strong>${state.wardrobe.length}</strong><span>в гардеробе</span></div></div>
      <div class="card stat-card"><div class="stat-icon">${icon("sparkle")}</div><div><strong>${available}</strong><span>готовы к выходу</span></div></div>
      <div class="card stat-card"><div class="stat-icon">${icon("heart")}</div><div><strong>${state.favorites.length}</strong><span>в избранном</span></div></div>
    </div>

    <div class="section-title">
      <div><h2>На сегодня</h2><p class="page-subtitle">Свежие сочетания под ваш день</p></div>
      <button class="text-link" data-page="plan" type="button">Все образы →</button>
    </div>

    ${state.homeError ? `<div class="card quick-card" style="margin-bottom:16px"><h3>Не удалось получить прогноз</h3><p>${escapeHTML(state.homeError)}</p><button class="button secondary small" data-page="plan" type="button">Выбрать место и дату</button></div>` : ""}

    ${cards.length ? `<div class="outfit-grid">${cards.join("")}</div>` : emptyState("Пока нет готовых образов", "Добавьте вещи в гардероб и выберите место — Clima подберёт сочетания по прогнозу погоды.", "Начать с гардероба", "go-wardrobe")}

    <div class="quick-grid">
      <div class="card quick-card"><h3>Добавить новую вещь</h3><p>Загрузите фото, укажите цвет и сезон — и вещь появится в вашем цифровом гардеробе.</p><button class="button secondary small" data-action="open-item" type="button">${icon("plus")}Добавить вещь</button></div>
      <div class="card quick-card"><h3>Ваш стиль — ваши правила</h3><p>Заполните предпочтения по стилю и цветам, чтобы рекомендации стали ещё персональнее.</p><button class="button secondary small" data-page="settings" type="button">Настроить профиль ${icon("arrow")}</button></div>
    </div>
  `;
  return shell(content);
}

export function planForm() {
  const place = state.selectedPlace;
  const occasion = state.planOccasion || "everyday";
  const placeValue = place
    ? `${place.name}${place.region ? `, ${place.region}` : ""}`
    : state.location;
  return `<form id="plan-form" class="card weather-form">
    <div class="form-row" style="display:flex; gap:16px; flex-wrap:nowrap; align-items:flex-start;">
      <div class="field" style="flex:0 0 auto;"><label for="place">Город/место</label><div class="autocomplete"><input id="place" name="place" placeholder="Начните вводить город" value="${escapeHTML(placeValue)}" required maxlength="200" autocomplete="off" data-lat="${escapeHTML(place?.lat ?? "")}" data-lon="${escapeHTML(place?.lon ?? "")}" /></div><small class="field-hint">При фокусе — города вашей страны; дальше — поиск по написанию.</small></div>
      <div class="field" style="flex:0 0 auto;"><label for="plan-date">Дата</label><input id="plan-date" type="date" name="date" value="${escapeHTML(state.planDate || today())}" required /></div>
      <div class="field" style="flex:0 0 auto;"><label for="occasion">Повод</label><select id="occasion" name="occasion">${OCCASIONS.map((o) => `<option value="${o.value}"${o.value === occasion ? " selected" : ""}>${escapeHTML(o.title)}</option>`).join("")}</select></div>
      <button class="button" type="submit" style="margin-top:18px;">${icon("sparkle")}Подобрать</button>
    </div>
  </form>`;
}

export async function renderPlan() {
  const uniqueOutfits = dedupeOutfits(state.outfits);
  const cards = await Promise.all(uniqueOutfits.map((outfit) => outfitCard(outfit)));
  return shell(`${heading("Образы по погоде", "Укажите место, дату и повод — подберём до трёх сочетаний из ваших вещей.")}${planForm()}${uniqueOutfits.length ? `<div class="section-title"><div><h2>Ваши сочетания</h2><p class="page-subtitle">Подходящие варианты из вашего гардероба</p></div></div><div class="outfit-grid">${cards.join("")}</div>` : emptyState("Готовы подобрать ваш образ?", "Вещи, сезон и прогноз погоды помогут найти сочетания, в которых будет комфортно.", "", "")}`);
}

export async function renderFavorites() {
  state.favorites = await request("/favorites");
  const data = await Promise.all(
    state.favorites.map(async (favorite) => ({
      favorite,
      outfit: await request(`/favorites/${favorite.id}`)
    }))
  );
  const cards = await Promise.all(
    data.map(({ favorite, outfit }) => outfitCard(outfit, favorite, false))
  );
  return shell(`${heading("Избранное", "Сохранённые образы можно менять, подбирая другие вещи из гардероба.")}${cards.length ? `<div class="outfit-grid">${cards.join("")}</div>` : emptyState("Здесь будут любимые образы", "Сохраняйте удачные сочетания после подбора, чтобы быстро вернуться к ним.", "Подобрать образ", "go-plan")}`);
}

export async function renderHistory() {
  state.history = await request("/outfits/history");
  const toRate = await request("/outfits/rate");
  // Подтягиваем избранное, чтобы у каждой карточки в истории
  // кнопка «Сохранить» была в правильном состоянии (закрашена/нет).
  if (!state.favorites?.length) {
    try { state.favorites = await request("/favorites"); }
    catch { state.favorites = []; }
  }
  const favoriteByOutfitId = new Map(
    (state.favorites || []).map((favorite) => [favorite.outfitId ?? favorite.outfit?.id ?? favorite.id, favorite])
  );

  const cards = await Promise.all(
    state.history.map((outfit) => outfitCard(outfit, favoriteByOutfitId.get(outfit.id) || null, false))
  );
  const ratingCards = await Promise.all(
    toRate.map((outfit) => outfitCard(outfit, favoriteByOutfitId.get(outfit.id) || null, false))
  );

  return shell(`${heading("История образов", "Все образы, которые вы выбирали. Оценки помогут персонализировать рекомендации.")}${toRate.length ? `<div class="section-title"><div><h2>Оцените недавнее</h2><p class="page-subtitle">Как вам эти образы?</p></div></div><div class="outfit-grid" style="margin-bottom:30px">${ratingCards.join("")}</div>` : ""}${cards.length ? `<div class="section-title"><div><h2>Выходы</h2><p class="page-subtitle">${itemCountLabel(cards.length)} сохранено в истории</p></div></div><div class="outfit-grid">${cards.join("")}</div>` : emptyState("История пока пуста", "Когда выберете образ, он появится здесь.", "Подобрать образ", "go-plan")}`);
}

async function ensureWardrobeReady() {
  if (!state.wardrobe?.length) {
    try {
      state.wardrobe = await request("/wardrobe");
    } catch {
      showToast("Не удалось загрузить гардероб. Проверьте соединение и попробуйте снова.", true);
      return false;
    }
  }
  const eligible = state.wardrobe.filter((item) => !item.inLaundry && !item.deleted);
  if (eligible.length === 0) {
    showToast("В гардеробе нет доступных вещей. Добавьте вещи в гардероб.", true);
    return false;
  }
  return true;
}

export async function submitPlan(event, rerender) {
  event.preventDefault();
  const form = event.target;
  if (form.dataset.submitting === "true") return;
  form.dataset.submitting = "true";

  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = "Подбираем…";

  if (!(await ensureWardrobeReady())) {
    delete form.dataset.submitting;
    button.disabled = false;
    button.innerHTML = `${icon("sparkle")}Подобрать`;
    return;
  }

  const data = new FormData(form);
  const placeInput = form.querySelector("#place");
  const params = new URLSearchParams({
    place: String(data.get("place")).trim(),
    date: String(data.get("date")),
    occasion: String(data.get("occasion") || "everyday")
  });

  let lat = placeInput?.dataset.lat || "";
  let lon = placeInput?.dataset.lon || "";
  if (!(lat && lon)) {
    try {
      const found = await request(`/places/search?q=${encodeURIComponent(params.get("place"))}&limit=1`);
      const list = Array.isArray(found) ? found : found?.suggestions || found?.places || found?.items || [];
      const first = list[0];
      if (first?.name && first.lat != null && first.lon != null) {
        setPlace(first);
        bindPlanPlace(first);
        params.set("place", `${first.name}${first.region ? `, ${first.region}` : ""}`);
        lat = String(first.lat);
        lon = String(first.lon);
      }
    } catch { /* без координат */ }
  }
  if (lat && lon) {
    params.set("lat", lat);
    params.set("lon", lon);
  }

  state.planDate = params.get("date");
  state.planOccasion = params.get("occasion");

  try {
    const picked = params.get("place");
    if (!state.selectedPlace || formatLoose(state.selectedPlace) !== picked) {
      state.location = picked.split(",")[0].trim();
    }
    await request("/profile/location", { method: "PUT", body: { location: state.location } });
    state.outfits = await request(`/outfits/plan?${params.toString()}`);

    if (state.outfits.length === 0) {
      showToast(`Для выбранной даты ${params.get("date")} и места ${picked} не удалось подобрать образ. Проверьте гардероб и попробуйте изменить дату или место.`);
    } else {
      showToast(`Подобрали образов: ${state.outfits.length}`);
    }
    await rerender();
  } catch (error) {
    state.outfits = [];
    try { await rerender(); } catch { /* ignore */ }
    showToast(String(error?.message || "Неизвестная ошибка"));
  } finally {
    if (form.isConnected) {
      delete form.dataset.submitting;
      button.disabled = false;
      button.innerHTML = `${icon("sparkle")}Подобрать`;
    }
  }
}

export async function composeOutfit() {
  if (!(await ensureWardrobeReady())) return;

  const eligible = state.wardrobe.filter((item) => !item.inLaundry && !item.deleted);
  const options = eligible
    .map((item) => `<label class="season-option"><input type="checkbox" name="compose-item" value="${item.id}" /><span>${escapeHTML(item.color)} ${escapeHTML(item.type)} · ${escapeHTML(PARTS[item.part] || "")}</span></label>`)
    .join("");
  const root = document.querySelector("#modal-root");
  if (!root) {
    console.error("Modal root element not found");
    return;
  }
  root.innerHTML = `<div class="modal-backdrop" data-action="backdrop"><section class="modal" role="dialog" aria-modal="true"><header class="modal-header"><div><h2>Собрать свой образ</h2><p class="page-subtitle">Отметьте вещи, из которых хотите собрать комплект.</p></div><button class="modal-close" data-action="close-modal" aria-label="Закрыть">${icon("close")}</button></header><form id="compose-form"><div class="season-options">${options || "<p>Нет чистых вещей в гардеробе.</p>"}</div><footer class="modal-footer"><button type="button" class="button secondary" data-action="close-modal">Отмена</button><button class="button" type="submit" ${eligible.length ? "" : "disabled"}>Проверить и сохранить</button></footer></form></section></div>`;
}

function formatLoose(place) {
  return place?.name ? `${place.name}${place.region ? `, ${place.region}` : ""}` : "";
}

export function bindPlanPlace(place) {
  const input = document.querySelector("#place");
  if (!input || !place) return;
  setPlace(place);
  input.dataset.lat = place.lat ?? "";
  input.dataset.lon = place.lon ?? "";
  input.value = formatLoose(place);
}

export async function saveComposedOutfit(event, rerender) {
  event.preventDefault();
  const itemIds = [...event.target.querySelectorAll('input[name="compose-item"]:checked')].map((input) => Number(input.value));
  try {
    const result = await request("/favorites/compose", { method: "POST", body: { itemIds } });
    document.querySelector("#modal-root").innerHTML = "";
    showToast(result?.favorite ? "Ваш образ собран и сохранён" : "Образ сохранён");
    state.page = "favorites";
    await rerender();
  } catch (error) {
    showToast(error.message, true);
  }
}
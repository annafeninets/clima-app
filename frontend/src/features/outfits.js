import { request } from "../core/api.js";
import { setPlace, state, PARTS } from "../core/state.js?v=20261008-03";
import { escapeHTML, humanDate, icon, itemCountLabel, showToast, today } from "../ui/helpers.js";
import { emptyState, heading, shell } from "../ui/layout.js";
import { OutfitCollage } from "./outfit-collage.js?v=20261008-01";

export const OCCASIONS = [
  { value: "everyday", title: "На каждый день" },
  { value: "work", title: "Работа" },
  { value: "casual", title: "Casual" },
  { value: "sport", title: "Спорт" },
  { value: "date", title: "Свидание" },
  { value: "formal", title: "Торжественный" },
  { value: "travel", title: "Путешествие" },
  { value: "party", title: "Вечеринка" },
  { value: "outdoor", title: "Прогулка / outdoor" },
];

function occasionLabel(value) {
  return OCCASIONS.find((item) => item.value === value)?.title || value || "";
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
  const favoriteButton = favorite
    ? `<button class="button danger small" data-action="remove-favorite" data-id="${favorite.id}">Убрать</button>`
    : `<button class="button secondary small" data-action="add-favorite" data-id="${outfit.id}">${icon("heart")}Сохранить</button>`;
  const rating =
    outfit.selected && !outfit.rating
      ? `<div class="rating" aria-label="Оценить образ">${[1, 2, 3, 4, 5]
          .map(
            (score) =>
              `<button title="${score}" data-action="rate" data-id="${outfit.id}" data-score="${score}">☆</button>`
          )
          .join("")}</div>`
      : outfit.rating
      ? `<span class="badge muted">Оценка ${outfit.rating}/5</span>`
      : "";
  const replacements = favorite
    ? (items || [])
        .map((item) => {
          const choices = state.wardrobe.filter(
            (candidate) =>
              candidate.part === item.part &&
              candidate.id !== item.id &&
              !candidate.inLaundry &&
              !candidate.deleted
          );
          if (!choices.length) return "";
          return `<div class="replace-row"><select aria-label="Заменить ${escapeHTML(item.type)}" id="replace-${favorite.id}-${item.id}"><option value="">Заменить ${escapeHTML(item.type)}</option>${choices
            .map(
              (choice) =>
                `<option value="${choice.id}">${escapeHTML(choice.color)} ${escapeHTML(choice.type)}</option>`
            )
            .join("")}</select><button class="button secondary small" data-action="replace-item" data-favorite="${favorite.id}" data-item="${item.id}">Ок</button></div>`;
        })
        .join("")
    : "";

  return `<article class="card outfit-card">
    ${collage}
    <div class="outfit-body"><div class="outfit-title"><h3>Образ на ${escapeHTML(humanDate(outfit.date))}</h3>${outfit.selected ? '<span class="badge">Выбран</span>' : ""}</div>
    <div class="outfit-meta">${escapeHTML(outfit.place || "")}${outfit.occasion ? ` · ${escapeHTML(occasionLabel(outfit.occasion))}` : ""}</div>
    <div class="item-chips">${items
      .map((item) => `<span class="chip">${escapeHTML(item.color || "")} ${escapeHTML(item.type || "")}</span>`)
      .join("")}</div>
    ${debugPanel(outfit)}
    <div class="outfit-actions">${allowSelect && !outfit.selected ? `<button class="button small" data-action="select-outfit" data-id="${outfit.id}">${icon("check")}Надела</button>` : ""}${favoriteButton}${rating}</div>
    ${replacements ? `<div>${replacements}</div>` : ""}
    </div></article>`;
}

export async function renderHome() {
  const available = state.wardrobe.filter((item) => !item.inLaundry && !item.deleted).length;
  const cards = await Promise.all(state.outfits.slice(0, 3).map((outfit) => outfitCard(outfit)));
  const content = `<section class="hero"><div class="hero-copy"><div class="hero-tag">${icon("sun")}В гармонии с погодой</div><h1>Хороший день начинается с образа</h1><p>Персональные сочетания из вашего гардероба — с учётом погоды, повода и того, что вам нравится.</p><button class="button" data-page="plan">Подобрать образ ${icon("arrow")}</button></div><div class="hero-art"><div class="sun-disc">${icon("sun")}</div><span class="floating-leaf"></span><span class="floating-leaf two"></span></div></section>
    <div class="stats-row"><div class="card stat-card"><div class="stat-icon">${icon("hanger")}</div><div><strong>${state.wardrobe.length}</strong><span>в гардеробе</span></div></div><div class="card stat-card"><div class="stat-icon">${icon("sparkle")}</div><div><strong>${available}</strong><span>готовы к выходу</span></div></div><div class="card stat-card"><div class="stat-icon">${icon("heart")}</div><div><strong>${state.favorites.length}</strong><span>в избранном</span></div></div></div>
    <div class="section-title"><div><h2>На сегодня</h2><p class="page-subtitle">Свежие сочетания под ваш день</p></div><button class="text-link" data-page="plan">Все образы →</button></div>
    ${state.homeError ? `<div class="card quick-card" style="margin-bottom:16px"><h3>Не удалось получить прогноз</h3><p>${escapeHTML(state.homeError)}</p><button class="button secondary small" data-page="plan">Выбрать место и дату</button></div>` : ""}
    ${cards.length ? `<div class="outfit-grid">${cards.join("")}</div>` : emptyState("Пока нет готовых образов", "Добавьте вещи в гардероб и выберите место — Clima подберёт сочетания по прогнозу погоды.", "Начать с гардероба", "go-wardrobe")}
    <div class="quick-grid" style="margin-top:22px"><div class="card quick-card"><h3>Добавить новую вещь</h3><p>Загрузите фото, укажите цвет и сезон — и вещь появится в вашем цифровом гардеробе.</p><button class="button secondary small" data-action="open-item">${icon("plus")}Добавить вещь</button></div><div class="card quick-card"><h3>Ваш стиль — ваши правила</h3><p>Заполните предпочтения по стилю и цветам, чтобы рекомендации стали ещё персональнее.</p><button class="button secondary small" data-page="settings">Настроить профиль ${icon("arrow")}</button></div></div>`;
  return shell(content);
}

export function planForm() {
  const place = state.selectedPlace;
  const occasion = state.planOccasion || "everyday";
  const occasionTitle = occasionLabel(occasion);
  return `<form id="plan-form" class="card weather-form"><div class="field"><label for="place">Город/место</label><div class="autocomplete"><input id="place" name="place" placeholder="Начните вводить город" value="${escapeHTML(place ? `${place.name}${place.region ? `, ${place.region}` : ""}` : state.location)}" required maxlength="200" autocomplete="off" data-lat="${escapeHTML(place?.lat ?? "")}" data-lon="${escapeHTML(place?.lon ?? "")}" /></div><small class="field-hint">При фокусе — города вашей страны; дальше — поиск по написанию.</small></div><div class="field"><label for="plan-date">Дата</label><input id="plan-date" type="date" name="date" value="${escapeHTML(state.planDate || today())}" required /></div><div class="field"><label for="occasion-input">Повод</label><div class="autocomplete"><input id="occasion-input" placeholder="Выберите или начните вводить" value="${escapeHTML(occasionTitle)}" maxlength="80" autocomplete="off" /><input type="hidden" id="occasion" name="occasion" value="${escapeHTML(occasion)}" /></div></div><button class="button" type="submit">${icon("sparkle")}Подобрать</button></form>`;
}

export async function renderPlan() {
  const cards = await Promise.all(state.outfits.map((outfit) => outfitCard(outfit)));
  return shell(`${heading("Образы по погоде", "Укажите место, дату и повод — подберём до трёх сочетаний из ваших вещей.")}${planForm()}${state.outfits.length ? `<div class="section-title"><div><h2>Ваши сочетания</h2><p class="page-subtitle">Подходящие варианты из вашего гардероба</p></div></div><div class="outfit-grid">${cards.join("")}</div>` : emptyState("Готовы подобрать ваш образ?", "Вещи, сезон и прогноз погоды помогут найти сочетания, в которых будет комфортно.", "", "")}`);
}

export async function renderFavorites() {
  state.favorites = await request("/favorites");
  const data = await Promise.all(
    state.favorites.map(async (favorite) => ({
      favorite,
      outfit: await request(`/favorites/${favorite.id}`),
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
  const cards = await Promise.all(state.history.map((outfit) => outfitCard(outfit, null, false)));
  const ratingCards = await Promise.all(toRate.map((outfit) => outfitCard(outfit, null, false)));
  return shell(`${heading("История образов", "Все образы, которые вы выбирали. Оценки помогут персонализировать рекомендации.")}${toRate.length ? `<div class="section-title"><div><h2>Оцените недавнее</h2><p class="page-subtitle">Как вам эти образы?</p></div></div><div class="outfit-grid" style="margin-bottom:30px">${ratingCards.join("")}</div>` : ""}${cards.length ? `<div class="section-title"><div><h2>Выходы</h2><p class="page-subtitle">${itemCountLabel(cards.length)} сохранено в истории</p></div></div><div class="outfit-grid">${cards.join("")}</div>` : emptyState("История пока пуста", "Когда выберете образ, он появится здесь.", "Подобрать образ", "go-plan")}`);
}

// Проверяем, что гардероба достаточно для генерации образа.
// Возвращает true, если можно продолжать, иначе показывает toast и false.
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
  const partsSet = new Set(eligible.map((item) => item.part));
  const required = ["TOP", "BOTTOM", "SHOES"];
  if (!required.every((part) => partsSet.has(part))) {
    showToast(
      "Недостаточно вещей в гардеробе для создания образа. Нужно хотя бы одно верха, низа и обуви.",
      true
    );
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
    occasion: String(data.get("occasion") || "everyday"),
  });

  // Координаты: сначала из выбранного города в автокомплите,
  // затем — из data-lat/lon самого input.
  const place = state.selectedPlace;
  const lat = placeInput?.dataset.lat || place?.lat;
  const lon = placeInput?.dataset.lon || place?.lon;
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
      showToast(
        `Для выбранной даты ${params.get("date")} и места ${picked} не удалось подобрать образ. Проверьте, пожалуйста, ваш гардероб на наличие подходящей одежды и попробуйте изменить дату или место.`
      );
    } else {
      showToast(`Подобрали образов: ${state.outfits.length}`);
    }
    await rerender();
  } catch (error) {
    const errorMessage = String(error?.message || "").toLowerCase();
    if (
      errorMessage.includes("weather") ||
      errorMessage.includes("forecast") ||
      errorMessage.includes("погод") ||
      errorMessage.includes("прогност")
    ) {
      showToast(
        "Не удалось получить прогноз погоды для выбранной даты и места. Пожалуйста, проверьте правильность введённого места и попробуйте другую дату."
      );
    } else {
      showToast(error.message, true);
    }
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
    .map(
      (item) =>
        `<label class="season-option"><input type="checkbox" name="compose-item" value="${item.id}" /><span>${escapeHTML(item.color)} ${escapeHTML(item.type)} · ${escapeHTML(PARTS[item.part] || "")}</span></label>`
    )
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
  const itemIds = [...event.target.querySelectorAll('input[name="compose-item"]:checked')].map(
    (input) => Number(input.value)
  );
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

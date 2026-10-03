import { request, photoUrl } from "../core/api.js";
import { state, PARTS, SEASONS, SEASON_LABELS } from "../core/state.js";
import { escapeHTML, fileAsDataUrl, icon, itemCountLabel, showToast } from "../ui/helpers.js";
import { emptyState, heading, shell } from "../ui/layout.js";

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
    <div class="toolbar"><div class="search-field">${icon("search")}<input id="wardrobe-search" placeholder="Найти вещь..." value="${escapeHTML(state.search)}" /></div><div class="filter-pills">${[["ALL", "Все"], ["TOP", "Верх"], ["BOTTOM", "Низ"], ["CLEAN", "Чистые"], ["LAUNDRY", "В стирке"]].map(([value, label]) => `<button class="filter-pill ${state.filter === value ? "active" : ""}" data-filter="${value}">${label}</button>`).join("")}</div></div>
    ${cards.length ? `<div class="wardrobe-grid">${cards.join("")}</div>` : emptyState(state.wardrobe.length ? "Ничего не найдено" : "Ваш гардероб ждёт первую вещь", state.wardrobe.length ? "Попробуйте изменить поиск или фильтр." : "Добавьте фото любимой вещи и укажите её характеристики — Clima позаботится об остальном.", state.wardrobe.length ? "" : "Добавить вещь", state.wardrobe.length ? "" : "open-item")}`);
}

export function openItemForm(item = {}) {
  const isEdit = Boolean(item.id);
  const checkedSeasons = item.seasons || [];
  const preview = item.photo?.startsWith("data:")
    ? `<div class="field wide"><img src="${escapeHTML(item.photo)}" style="width:84px;height:84px;border-radius:12px;object-fit:cover" alt="Фото вещи" /></div>` : "";
  const form = `<form id="item-form" data-id="${item.id || ""}"><div class="form-grid">
    <label class="file-drop wide" for="item-photo">${icon("image")}<span id="file-label">${isEdit ? "Заменить фото (необязательно)" : "Загрузить фото · PNG, JPEG, GIF или WebP, до 5 МБ"}</span><input id="item-photo" name="photo" type="file" accept="image/png,image/jpeg,image/gif,image/webp" ${isEdit ? "" : "required"} /></label>
    ${preview}
    <div class="field"><label for="item-type">Тип вещи</label><input id="item-type" name="type" required maxlength="100" value="${escapeHTML(item.type || "")}" placeholder="Например, футболка" /></div>
    <div class="field"><label for="item-color">Цвет</label><input id="item-color" name="color" required maxlength="100" value="${escapeHTML(item.color || "")}" placeholder="Например, белый" /></div>
    <div class="field"><label for="item-part">Часть образа</label><select id="item-part" name="part"><option value="TOP" ${item.part !== "BOTTOM" ? "selected" : ""}>Верх</option><option value="BOTTOM" ${item.part === "BOTTOM" ? "selected" : ""}>Низ</option></select></div>
    <div class="field"><label for="item-dress">Повод / дресс-код</label><input id="item-dress" name="dressCode" value="${escapeHTML(item.dressCode || "casual")}" maxlength="100" /></div>
    <div class="field wide"><span class="field-label">Сезоны</span><div class="season-options">${SEASONS.map((season) => `<label class="season-option"><input type="checkbox" name="seasons" value="${season}" ${checkedSeasons.includes(season) || (!item.id && season !== "WINTER") ? "checked" : ""} /><span>${SEASON_LABELS[season]}</span></label>`).join("")}</div></div>
    <div class="field"><label for="min-temp">От, °C</label><input id="min-temp" name="minTemperature" type="number" required value="${item.minTemperature ?? -10}" /></div>
    <div class="field"><label for="max-temp">До, °C</label><input id="max-temp" name="maxTemperature" type="number" required value="${item.maxTemperature ?? 40}" /></div>
    <div class="field"><label for="item-style">Стиль</label><input id="item-style" name="style" maxlength="100" value="${escapeHTML(item.style || "")}" /></div>
    <div class="field"><label for="item-material">Материал</label><input id="item-material" name="material" maxlength="100" value="${escapeHTML(item.material || "")}" /></div>
    <div class="field"><label for="item-silhouette">Силуэт</label><input id="item-silhouette" name="silhouette" maxlength="100" value="${escapeHTML(item.silhouette || "")}" /></div>
    <div class="field"><label for="item-laundry">Стирка</label><select id="item-laundry" name="inLaundry"><option value="false" ${!item.inLaundry ? "selected" : ""}>Чистая</option><option value="true" ${item.inLaundry ? "selected" : ""}>В стирке</option></select></div>
    </div><div class="modal-footer"><button class="button secondary" type="button" data-action="close-modal">Отмена</button>${isEdit ? `<button class="button danger" type="button" data-action="delete-item" data-id="${item.id}">Удалить</button>` : ""}<button class="button" type="submit">${isEdit ? "Сохранить" : "Добавить в гардероб"}</button></div></form>`;
  const root = document.querySelector("#modal-root");
  root.innerHTML = `<div class="modal-backdrop" data-action="backdrop"><section class="modal" role="dialog" aria-modal="true"><header class="modal-header"><div><h2>${isEdit ? "Редактировать вещь" : "Новая вещь"}</h2><p class="page-subtitle">Добавьте фото и характеристики — они помогут подобрать образ.</p></div><button class="modal-close" data-action="close-modal" aria-label="Закрыть">${icon("close")}</button></header>${form}</section></div>`;
  root.querySelector(".modal").addEventListener("click", (event) => event.stopPropagation());
}

export async function saveItem(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const id = form.dataset.id;
  const file = data.get("photo");
  try {
    let photo = "";
    if (file instanceof File && file.size) {
      if (file.size > 5 * 1024 * 1024) throw new Error("Размер фото не должен превышать 5 МБ");
      photo = await fileAsDataUrl(file);
    }
    const card = {
      type: String(data.get("type")).trim(), color: String(data.get("color")).trim(),
      part: data.get("part"), seasons: data.getAll("seasons"),
      minTemperature: Number(data.get("minTemperature")), maxTemperature: Number(data.get("maxTemperature")),
      dressCode: String(data.get("dressCode") || "casual").trim(), style: String(data.get("style") || "").trim(),
      material: String(data.get("material") || "").trim(), silhouette: String(data.get("silhouette") || "").trim()
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
    showToast(error.message, true);
    return false;
  }
}

export async function changeLaundry(id, value) {
  await request(`/wardrobe/items/${id}/laundry`, { method: "PUT", body: { value } });
}

export async function deleteItem(id) {
  await request(`/wardrobe/items/${id}`, { method: "DELETE" });
}

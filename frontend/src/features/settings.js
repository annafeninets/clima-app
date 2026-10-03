import { request } from "../core/api.js";
import { state, STORAGE_KEYS } from "../core/state.js";
import { escapeHTML, showToast } from "../ui/helpers.js";
import { heading, shell } from "../ui/layout.js";

const PROFILE_SUGGESTIONS = {
  location: ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск"],
  style: [
    "Классический", "Casual", "Спортивный", "Минимализм", "Романтический",
    "Деловой", "Уличный", "Бохо", "Базовый", "Повседневный", "Элегантный",
    "Офисный", "Preppy", "Гранж", "Винтажный", "Ретро", "Рок", "Авангардный",
    "Скандинавский", "Тихая роскошь"
  ],
  colors: [
    "Белый", "Молочный", "Чёрный", "Серый", "Бежевый", "Коричневый", "Шоколадный",
    "Синий", "Голубой", "Зелёный", "Оливковый", "Красный", "Бордовый", "Розовый",
    "Пудровый", "Жёлтый", "Горчичный", "Оранжевый", "Фиолетовый", "Сиреневый"
  ],
  sizes: ["XS", "S", "M", "L", "XL", "XXL", "34", "36", "38", "40", "42", "44", "46"],
  bodyFeatures: [
    "Прямой", "Свободный", "Приталенный", "Oversize", "Облегающий", "Широкий",
    "А-силуэт", "Relaxed", "Полуприлегающий", "Slim fit", "Regular fit",
    "Высокая посадка", "Средняя посадка", "Низкая посадка"
  ]
};

function profileField(name, label, value, placeholder, wide = false) {
  const suggestions = PROFILE_SUGGESTIONS[name];
  const listId = `profile-${name}-suggestions`;
  return `<div class="field ${wide ? "wide" : ""}"><label for="profile-${name}">${label}</label><input id="profile-${name}" name="${name}" value="${escapeHTML(value)}" placeholder="${placeholder}" maxlength="${name === "location" ? 200 : 500}" ${name === "location" ? "required" : ""} list="${listId}" aria-describedby="profile-${name}-hint profile-${name}-error" autocomplete="off" /><datalist id="${listId}">${suggestions.map((option) => `<option value="${escapeHTML(option)}"></option>`).join("")}</datalist><small class="field-hint" id="profile-${name}-hint">${name === "location" ? "Начните вводить город или выберите из списка." : "Можно выбрать вариант или перечислить несколько через запятую."}</small><small class="field-error" id="profile-${name}-error" aria-live="polite"></small></div>`;
}

export async function renderSettings() {
  [state.profile, state.settings] = await Promise.all([request("/profile"), request("/settings")]);
  state.theme = state.settings.theme || state.theme;
  localStorage.setItem(STORAGE_KEYS.theme, state.theme);
  document.documentElement.dataset.theme = state.theme;

  const tabs = [["profile", "Профиль и стиль"], ["notifications", "Уведомления"], ["appearance", "Внешний вид"], ["account", "Аккаунт"]];
  let panel = "";
  if (state.settingsTab === "profile") {
    panel = `<h2>О вас и вашем стиле</h2><p class="page-subtitle">Эти данные помогают выбирать сочетания, которые нравятся именно вам.</p><form id="profile-form" class="form-grid" novalidate>${profileField("location", "Ваш город", state.location, "Например, Санкт-Петербург", true)}${profileField("style", "Стиль", state.profile.style, "Например, casual, минимализм")}${profileField("colors", "Любимые цвета", state.profile.colors, "Например, зелёный, бежевый")}${profileField("sizes", "Размеры", state.profile.sizes, "Например, M, 38")}${profileField("bodyFeatures", "Предпочтительный силуэт", state.profile.bodyFeatures, "Например, прямой, свободный")}<div class="form-errors wide" id="profile-form-errors" role="alert" aria-live="polite"></div><div class="wide"><button class="button" type="submit">Сохранить изменения</button></div></form>`;
  } else if (state.settingsTab === "notifications") {
    panel = `<h2>Утренний аутфит</h2><p class="page-subtitle">Настройте ежедневное уведомление. Push-уведомления доступны, если они настроены для приложения.</p><form id="notification-form"><div class="switch-row"><div><strong>Ежедневное уведомление</strong><div class="field-hint">Напоминать проверить образ на день</div></div><input class="switch" type="checkbox" name="enabled" ${state.settings.notificationsEnabled ? "checked" : ""} /></div><div class="form-grid" style="margin:18px 0"><div class="field"><label for="notificationTime">Время</label><input id="notificationTime" type="time" name="time" value="${escapeHTML(String(state.settings.notificationTime || "07:00").slice(0, 5))}" /></div><div class="field"><label for="timeZone">Часовой пояс</label><input id="timeZone" name="timeZone" value="${escapeHTML(state.settings.timeZone || "UTC")}" placeholder="Europe/Moscow" /></div></div><button class="button" type="submit">Сохранить настройки</button></form>${state.publicVapidKey ? `<button class="button secondary small" style="margin-top:16px" data-action="subscribe-push">Подключить push-уведомления</button>` : `<p class="field-hint" style="margin-top:16px">Push-уведомления не настроены для этого приложения.</p>`}`;
  } else if (state.settingsTab === "appearance") {
    panel = `<h2>Внешний вид</h2><p class="page-subtitle">Выберите комфортную тему интерфейса.</p><div class="filter-pills"><button class="filter-pill ${state.settings.theme === "LIGHT" ? "active" : ""}" data-theme-set="LIGHT">Светлая</button><button class="filter-pill ${state.settings.theme === "DARK" ? "active" : ""}" data-theme-set="DARK">Тёмная</button></div>`;
  } else {
    panel = `<h2>Управление аккаунтом</h2><p class="page-subtitle">Войдите как <strong>${escapeHTML(state.login)}</strong>. Удаление аккаунта необратимо удалит ваши данные.</p><button class="button danger" data-action="delete-account">Удалить аккаунт</button>`;
  }
  return shell(`${heading("Настройки", "Профиль, уведомления и внешний вид приложения.")}<div class="settings-layout"><nav class="card settings-tabs">${tabs.map(([id, title]) => `<button class="settings-tab ${state.settingsTab === id ? "active" : ""}" data-settings-tab="${id}">${title}</button>`).join("")}</nav><section class="card settings-panel">${panel}</section></div>`);
}

export async function saveProfile(event, rerender) {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector('button[type="submit"]');
  const originalButtonText = submitButton.textContent;
  const data = new FormData(form);
  const values = Object.fromEntries(
    ["location", "style", "colors", "sizes", "bodyFeatures"].map((name) =>
      [name, String(data.get(name) || "").trim()]
    )
  );
  const errors = form.querySelector("#profile-form-errors");
  const invalid = Object.entries(values).find(([name, value]) => profileFieldError(name, value));
  for (const [name, value] of Object.entries(values)) {
    form.elements.namedItem(name).dataset.touched = "true";
    updateProfileFieldError(form, name, value);
  }
  if (invalid) {
    const [name, value] = invalid;
    errors.textContent = profileFieldError(name, value);
    form.elements.namedItem(name).focus();
    return;
  }
  const location = values.location;
  submitButton.disabled = true;
  submitButton.textContent = "Сохранение…";
  try {
    await request("/profile", { method: "PUT", body: {
      style: values.style, colors: values.colors,
      sizes: values.sizes, bodyFeatures: values.bodyFeatures
    } });
    if (location) await request("/profile/location", { method: "PUT", body: { location } });
    else if (state.location) throw new Error("Укажите город");
    state.location = location;
    showToast("Профиль сохранён");
    await rerender();
  } catch (error) {
    errors.textContent = error.message || "Не удалось сохранить профиль.";
    showToast(errors.textContent, true);
  } finally {
    if (submitButton.isConnected) {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  }
}

function profileFieldError(name, value) {
  if (name === "location") {
    if (!value) return "Укажите город.";
    if (value.length < 2 || value.length > 200 || !/[\p{L}]/u.test(value) ||
        !/^[\p{L}\p{M}\s.'’-]+$/u.test(value)) {
      return "Введите название города буквами (можно использовать пробел и дефис).";
    }
    return "";
  }
  if (!value) return "";
  if (value.length > 500) return "Значение не должно превышать 500 символов.";
  const entries = value.split(",").map((entry) => entry.trim());
  if (entries.some((entry) => !entry)) {
    return "Разделяйте несколько значений запятыми и не оставляйте пустые пункты.";
  }
  if (name === "sizes") {
    return entries.every((entry) => /^[\p{L}\p{M}\p{N}][\p{L}\p{M}\p{N}\s./+-]*$/u.test(entry))
      ? ""
      : "Укажите размер буквами или цифрами, например M, 38.";
  }
  return entries.every((entry) =>
    /[\p{L}]/u.test(entry) && /^[\p{L}\p{M}\p{N}\s.'’()/-]+$/u.test(entry)
  )
    ? ""
    : "Для каждого варианта используйте осмысленный текст из букв, цифр и обычных разделителей.";
}

function updateProfileFieldError(form, name, value) {
  const input = form.elements.namedItem(name);
  const message = profileFieldError(name, value.trim());
  input.setAttribute("aria-invalid", String(Boolean(message)));
  form.querySelector(`#profile-${name}-error`).textContent = message;
}

export function validateProfileFieldInput(input, markTouched = false) {
  if (!input?.form || input.form.id !== "profile-form" ||
      !Object.hasOwn(PROFILE_SUGGESTIONS, input.name)) return;
  if (markTouched) input.dataset.touched = "true";
  if (input.dataset.touched === "true") {
    updateProfileFieldError(input.form, input.name, input.value);
  }
  input.form.querySelector("#profile-form-errors").textContent = "";
}

export async function saveNotifications(event, rerender) {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  try {
    await request("/settings/notifications", { method: "PUT", body: {
      enabled: data.get("enabled") === "on", time: data.get("time") || "07:00",
      timeZone: String(data.get("timeZone") || "UTC").trim()
    } });
    showToast("Настройки уведомлений сохранены");
    await rerender();
  } catch (error) { showToast(error.message, true); }
}

function decodeVapidKey(value) {
  const padding = "=".repeat((4 - value.length % 4) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
}

export async function subscribePush() {
  const key = state.publicVapidKey.trim();
  if (!key) throw new Error("Push-уведомления не настроены для этого приложения.");
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new Error("Этот браузер не поддерживает Web Push.");
  }
  if (!window.isSecureContext) throw new Error("Web Push работает только через HTTPS или localhost.");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Разрешите уведомления в настройках браузера.");
  const registration = await navigator.serviceWorker.register("/service-worker.js");
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: decodeVapidKey(key)
  });
  await request("/push/subscriptions", { method: "POST", body: subscription.toJSON() });
  showToast("Push-уведомления подключены");
}

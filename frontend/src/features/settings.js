import { request } from "../core/api.js";
import { state, STORAGE_KEYS } from "../core/state.js?v=20261008-03";
import { escapeHTML, showToast } from "../ui/helpers.js";
import { heading, shell } from "../ui/layout.js";
import {
  getCurrentSubscription, isIOSWithoutPWA, isPushSupported, requestNotificationPermission,
  sendSubscriptionToServer, subscribeToPush, unsubscribeFromPush
} from "./push.js?v=20261008-02";

const FALLBACK_TIME_ZONES = [
  "Europe/Moscow", "Europe/Kaliningrad", "Europe/Samara", "Asia/Yekaterinburg",
  "Asia/Novosibirsk", "Asia/Vladivostok", "Asia/Almaty", "Asia/Tbilisi",
  "America/New_York", "America/Chicago", "America/Los_Angeles", "UTC"
];

function timeZoneOptions(selected) {
  let zones = FALLBACK_TIME_ZONES;
  if (typeof Intl.supportedValuesOf === "function") {
    zones = [...new Set(["UTC", ...Intl.supportedValuesOf("timeZone")])];
  }
  if (selected && !zones.includes(selected)) zones.push(selected);
  return zones.map((zone) =>
    `<option value="${escapeHTML(zone)}" ${zone === selected ? "selected" : ""}>${escapeHTML(zone)}</option>`
  ).join("");
}

function notificationStatusMarkup() {
  if (!isPushSupported()) {
    return `<div class="push-status error" role="status">Ваш браузер не поддерживает уведомления.</div>`;
  }
  if (isIOSWithoutPWA()) {
    return `<div class="push-status ios" role="status"><strong>ⓘ Уведомления на iPhone</strong><span>Чтобы получать уведомления на iPhone, добавьте Clima на рабочий стол: нажмите «Поделиться» в Safari → «На экран Домой».</span></div>`;
  }
  if (state.settings.notificationsEnabled && state.settings.pushSubscribed) {
    return `<div class="push-status success" role="status">Уведомления подключены</div>`;
  }
  if (Notification.permission === "denied") {
    return `<div class="push-status error" role="status">Уведомления отключены в настройках браузера.</div>`;
  }
  if (!state.publicVapidKey) {
    return `<div class="push-status info" role="status">Подключение уведомлений пока недоступно.</div>`;
  }
  return `<div class="push-status info" id="push-status" role="status" aria-live="polite"></div>`;
}

function wardrobeStatusMarkup(status) {
  if (status?.is_complete) return "";
  const labels = {
    top: "верх", outerwear: "верхнюю одежду", bottom: "низ",
    shoes: "обувь", bag: "сумку", hat: "головной убор", accessories: "аксессуары"
  };
  const missing = (status?.missing || []).map((category) => labels[category] || category);
  if (!missing.length) return "";
  return `<div class="wardrobe-status-warning" role="status">Чтобы получать образы, добавьте: ${escapeHTML(missing.join(", "))}</div>`;
}

const PROFILE_SUGGESTIONS = {
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
  const showDataList = Boolean(suggestions);
  const locationField = name === "location"
    ? `<div class="autocomplete"><input id="profile-${name}" name="${name}" value="${escapeHTML(value)}" placeholder="${placeholder}" maxlength="200" required autocomplete="off" aria-describedby="profile-${name}-hint profile-${name}-error" /></div>`
    : `<input id="profile-${name}" name="${name}" value="${escapeHTML(value)}" placeholder="${placeholder}" maxlength="500" ${showDataList ? `list="${listId}"` : ""} aria-describedby="profile-${name}-hint profile-${name}-error" autocomplete="off" />`;
  return `<div class="field ${wide ? "wide" : ""}"><label for="profile-${name}">${label}</label>${locationField}${showDataList && name !== "location" ? `<datalist id="${listId}">${suggestions.map((option) => `<option value="${escapeHTML(option)}"></option>`).join("")}</datalist>` : ""}<small class="field-hint" id="profile-${name}-hint">${name === "location" ? "Начните вводить город или выберите из подсказок." : "Можно выбрать вариант или перечислить несколько через запятую."}</small><small class="field-error" id="profile-${name}-error" aria-live="polite"></small></div>`;
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
    const detectedTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    const savedTimeZone = localStorage.getItem(STORAGE_KEYS.timeZone);
    const selectedTimeZone = savedTimeZone === state.settings.timeZone
      ? savedTimeZone
      : state.settings.timeZone === "UTC" && detectedTimeZone !== "UTC"
        ? detectedTimeZone
        : state.settings.timeZone || detectedTimeZone;
    const permission = isPushSupported() ? Notification.permission : "unsupported";
    panel = `<h2>Утренний аутфит</h2><p class="page-subtitle">Ежедневное напоминание посмотреть образ на день</p><form id="notification-form"><label class="notification-switch-row" for="morning-notification-toggle"><span><strong>Ежедневное уведомление</strong><span class="field-hint">Одно напоминание в выбранное время</span></span><input id="morning-notification-toggle" class="switch" type="checkbox" name="enabled" role="switch" aria-checked="${state.settings.notificationsEnabled}" ${state.settings.notificationsEnabled ? "checked" : ""} /></label>${notificationStatusMarkup()}${wardrobeStatusMarkup(state.wardrobeStatus)}<div class="form-grid notification-fields"><div class="field"><label for="notificationTime">Время</label><input id="notificationTime" type="time" name="time" value="${escapeHTML(String(state.settings.notificationTime || "07:00").slice(0, 5))}" /></div><div class="field"><label for="timeZone">Часовой пояс</label><select id="timeZone" name="timeZone">${timeZoneOptions(selectedTimeZone)}</select></div></div><button class="button notification-save" type="submit">Сохранить настройки</button></form>${permission === "default" && isPushSupported() && state.publicVapidKey && !isIOSWithoutPWA() ? `<button class="button notification-connect" data-action="subscribe-push" type="button">Подключить push-уведомления</button>` : ""}`;
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
  const form = event.currentTarget;
  const data = new FormData(form);
  const settings = {
    enabled: data.get("enabled") === "on",
    time: data.get("time") || "07:00",
    timeZone: String(data.get("timeZone") || "UTC").trim()
  };
  try {
    localStorage.setItem(STORAGE_KEYS.timeZone, settings.timeZone);
    let result;
    if (settings.enabled) {
      const subscription = await getCurrentSubscription();
      if (subscription) result = await sendSubscriptionToServer(subscription, settings);
      else result = await request("/settings/notifications", { method: "PUT", body: settings });
    } else {
      result = await request("/settings/notifications", { method: "PUT", body: settings });
    }
    showToast(result?.limit_reached
      ? "Достигнут лимит уведомлений на сегодня"
      : "Настройки сохранены", Boolean(result?.limit_reached));
    await rerender();
  } catch { showToast("Не удалось сохранить настройки. Проверьте данные и попробуйте ещё раз.", true); }
}

function currentFormSettings(form) {
  const data = new FormData(form);
  return {
    enabled: true,
    time: data.get("time") || "07:00",
    timeZone: String(data.get("timeZone") || "UTC").trim()
  };
}

function showPushStatus(message, type = "info") {
  const status = document.querySelector("#push-status");
  if (!status) return;
  status.className = `push-status ${type}`;
  status.textContent = message;
}

async function enableNotifications(form, rerender) {
  const toggle = form.querySelector('[name="enabled"]');
  if (!isPushSupported()) {
    toggle.checked = false;
    toggle.setAttribute("aria-checked", "false");
    showPushStatus("Ваш браузер не поддерживает уведомления.", "error");
    return;
  }
  if (isIOSWithoutPWA()) {
    toggle.checked = false;
    toggle.setAttribute("aria-checked", "false");
    showPushStatus("ⓘ Чтобы получать уведомления на iPhone, добавьте Clima на рабочий стол: нажмите «Поделиться» в Safari → «На экран Домой».", "ios");
    return;
  }
  if (!window.isSecureContext) {
    toggle.checked = false;
    toggle.setAttribute("aria-checked", "false");
    showPushStatus("Для уведомлений нужно открыть Clima по защищённому соединению.", "error");
    return;
  }
  if (!state.publicVapidKey) {
    toggle.checked = false;
    toggle.setAttribute("aria-checked", "false");
    showPushStatus("Подключение уведомлений пока недоступно.", "info");
    return;
  }
  toggle.disabled = true;
  showPushStatus("Подключаем уведомления…");
  try {
    const permission = await requestNotificationPermission();
    if (permission !== "granted") {
      toggle.checked = false;
      toggle.setAttribute("aria-checked", "false");
      showPushStatus("Уведомления отключены в настройках браузера.", "error");
      return;
    }
    const settings = currentFormSettings(form);
    localStorage.setItem(STORAGE_KEYS.timeZone, settings.timeZone);
    const subscription = await subscribeToPush(state.publicVapidKey);
    const result = await sendSubscriptionToServer(subscription, settings);
    showToast(result?.limit_reached
      ? "Достигнут лимит уведомлений на сегодня"
      : "Уведомления подключены", Boolean(result?.limit_reached));
    await rerender();
  } catch {
    toggle.checked = false;
    toggle.setAttribute("aria-checked", "false");
    showPushStatus("Не удалось подключить уведомления. Проверьте соединение и повторите попытку.", "error");
  } finally {
    if (toggle.isConnected) toggle.disabled = false;
  }
}

export async function handleNotificationToggle(event, rerender) {
  const toggle = event.target;
  if (toggle.id !== "morning-notification-toggle") return;
  toggle.setAttribute("aria-checked", String(toggle.checked));
  const form = toggle.form;
  if (toggle.checked) {
    await enableNotifications(form, rerender);
    return;
  }
  toggle.disabled = true;
  let settingsSaved = false;
  try {
    const settings = currentFormSettings(form);
    settings.enabled = false;
    await request("/settings/notifications", { method: "PUT", body: settings });
    settingsSaved = true;
    await request("/push/subscriptions", { method: "DELETE" });
    if (isPushSupported()) await unsubscribeFromPush();
    showToast("Уведомления отключены");
    await rerender();
  } catch {
    if (settingsSaved) {
      showToast("Уведомления выключены, но подписку браузера не удалось удалить.", true);
      await rerender();
    } else {
      toggle.checked = true;
      toggle.setAttribute("aria-checked", "true");
      showPushStatus("Не удалось обновить настройки уведомлений. Попробуйте ещё раз.", "error");
    }
  } finally {
    if (toggle.isConnected) toggle.disabled = false;
  }
}

export async function connectPush(rerender) {
  const form = document.querySelector("#notification-form");
  if (form) await enableNotifications(form, rerender);
}

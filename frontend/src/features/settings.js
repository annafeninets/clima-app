import { request } from "../core/api.js";
import { state, STORAGE_KEYS } from "../core/state.js";
import { escapeHTML, showToast } from "../ui/helpers.js";
import { heading, shell } from "../ui/layout.js";

export async function renderSettings() {
  [state.profile, state.settings] = await Promise.all([request("/profile"), request("/settings")]);
  state.theme = state.settings.theme || state.theme;
  localStorage.setItem(STORAGE_KEYS.theme, state.theme);
  document.documentElement.dataset.theme = state.theme;

  const tabs = [["profile", "Профиль и стиль"], ["notifications", "Уведомления"], ["appearance", "Внешний вид"], ["account", "Аккаунт"]];
  let panel = "";
  if (state.settingsTab === "profile") {
    panel = `<h2>О вас и вашем стиле</h2><p class="page-subtitle">Эти данные помогают выбирать сочетания, которые нравятся именно вам.</p><form id="profile-form" class="form-grid" novalidate><div class="field wide"><label for="location">Ваш город</label><input id="location" name="location" value="${escapeHTML(state.location)}" placeholder="Например, Санкт-Петербург" maxlength="200" required /></div><div class="field"><label for="style">Стиль</label><input id="style" name="style" value="${escapeHTML(state.profile.style)}" placeholder="casual, minimal" maxlength="500" /></div><div class="field"><label for="colors">Любимые цвета</label><input id="colors" name="colors" value="${escapeHTML(state.profile.colors)}" placeholder="зелёный, бежевый" maxlength="500" /></div><div class="field"><label for="sizes">Размеры</label><input id="sizes" name="sizes" value="${escapeHTML(state.profile.sizes)}" placeholder="M, 38" maxlength="500" /></div><div class="field"><label for="bodyFeatures">Особенности фигуры</label><input id="bodyFeatures" name="bodyFeatures" value="${escapeHTML(state.profile.bodyFeatures)}" placeholder="relaxed, regular" maxlength="500" /></div><div class="form-errors wide" id="profile-form-errors" role="alert" aria-live="polite"></div><div class="wide"><button class="button" type="submit">Сохранить изменения</button></div></form>`;
  } else if (state.settingsTab === "notifications") {
    panel = `<h2>Утренний аутфит</h2><p class="page-subtitle">Настройте ежедневное уведомление. Для push нужны HTTPS (или localhost), Service Worker и публичный VAPID-ключ.</p><form id="notification-form"><div class="switch-row"><div><strong>Ежедневное уведомление</strong><div class="field-hint">Напоминать проверить образ на день</div></div><input class="switch" type="checkbox" name="enabled" ${state.settings.notificationsEnabled ? "checked" : ""} /></div><div class="form-grid" style="margin:18px 0"><div class="field"><label for="notificationTime">Время</label><input id="notificationTime" type="time" name="time" value="${escapeHTML(String(state.settings.notificationTime || "07:00").slice(0, 5))}" /></div><div class="field"><label for="timeZone">Часовой пояс</label><input id="timeZone" name="timeZone" value="${escapeHTML(state.settings.timeZone || "UTC")}" placeholder="Europe/Moscow" /></div></div><button class="button" type="submit">Сохранить настройки</button></form><div class="auth-api"><label for="vapid-public-key">Публичный VAPID-ключ (не приватный)</label><input id="vapid-public-key" value="${escapeHTML(state.publicVapidKey)}" placeholder="Настраивается при развёртывании" /><button class="button secondary small" style="margin-top:10px" data-action="subscribe-push">Подключить push-уведомления</button></div>`;
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
  const data = new FormData(form);
  const values = Object.fromEntries(
    ["location", "style", "colors", "sizes", "bodyFeatures"].map((name) =>
      [name, String(data.get(name) || "").trim()]
    )
  );
  const errors = form.querySelector("#profile-form-errors");
  const invalid = Object.entries(values).find(([name, value]) => profileFieldError(name, value));
  if (invalid) {
    const [name, value] = invalid;
    errors.textContent = profileFieldError(name, value);
    form.elements.namedItem(name).focus();
    return;
  }
  const location = values.location;
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
  } catch (error) { showToast(error.message, true); }
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
  if (name === "sizes") {
    return /^[\p{L}\p{M}\p{N}\s,./+-]+$/u.test(value) && /[\p{L}\p{N}]/u.test(value)
      ? ""
      : "Укажите размер буквами или цифрами, например M, 38.";
  }
  return /[\p{L}]/u.test(value) && /^[\p{L}\p{M}\p{N}\s,.'’()/-]+$/u.test(value)
    ? ""
    : "Используйте буквы, цифры и обычные разделители.";
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
  const input = document.querySelector("#vapid-public-key");
  const key = input?.value.trim() || "";
  if (!key) throw new Error("Укажите публичный VAPID-ключ, соответствующий ключу backend.");
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new Error("Этот браузер не поддерживает Web Push.");
  }
  if (!window.isSecureContext) throw new Error("Web Push работает только через HTTPS или localhost.");
  state.publicVapidKey = key;
  localStorage.setItem(STORAGE_KEYS.vapid, key);
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

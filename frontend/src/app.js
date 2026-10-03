import { ApiError, request } from "./core/api.js";
import { state, clearSession, STORAGE_KEYS } from "./core/state.js";
import { renderAuth, submitAuth, toggleAuthMode, logout } from "./features/auth.js?v=20261003-6";
import {
  composeOutfit, renderFavorites, renderHistory, renderHome, renderPlan, saveComposedOutfit, submitPlan
} from "./features/outfits.js";
import {
  changeLaundry, deleteItem, openItemForm, renderWardrobe
} from "./features/wardrobe.js?v=20261003-9";
import {
  renderSettings, saveNotifications, saveProfile, subscribePush
} from "./features/settings.js";
import { showToast } from "./ui/helpers.js";
import { loadingError, shell } from "./ui/layout.js";

const app = document.querySelector("#app");

function mountAuth() {
  app.innerHTML = renderAuth();
  app.querySelector("#auth-form")?.addEventListener("submit", (event) => submitAuth(event, render));
  app.querySelector('[data-action="toggle-auth"]')?.addEventListener("click", () => {
    toggleAuthMode();
    mountAuth();
  });
}

async function render() {
  document.documentElement.dataset.theme = state.theme;
  if (!state.token) {
    mountAuth();
    return;
  }

  app.innerHTML = `<div class="loading"><span class="spinner"></span></div>`;
  try {
    state.location = (await request("/profile/location"))?.location || "";
    if (["home", "wardrobe", "favorites"].includes(state.page)) {
      state.wardrobe = await request("/wardrobe");
    }
    if (state.page === "home") {
      state.homeError = "";
      if (state.location) {
        try {
          state.outfits = await request(`/outfits/today?location=${encodeURIComponent(state.location)}`);
        } catch (error) {
          state.homeError = error.message;
          state.outfits = [];
        }
      } else {
        state.outfits = [];
        state.homeError = "Укажите ваш город в настройках профиля, чтобы построить образ по прогнозу.";
      }
      try { state.favorites = await request("/favorites"); }
      catch { state.favorites = []; }
      app.innerHTML = await renderHome();
    } else if (state.page === "plan") app.innerHTML = await renderPlan();
    else if (state.page === "wardrobe") app.innerHTML = await renderWardrobe();
    else if (state.page === "favorites") app.innerHTML = await renderFavorites();
    else if (state.page === "history") app.innerHTML = await renderHistory();
    else if (state.page === "settings") app.innerHTML = await renderSettings();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearSession();
      return render();
    }
    app.innerHTML = shell(`<div class="page-heading"><div><h1>Не удалось загрузить данные</h1><p class="page-subtitle">Проверьте соединение с backend и попробуйте ещё раз.</p></div></div>${loadingError(error.message)}`);
  }
}

async function handleAction(element, event) {
  const action = element.dataset.action;
  try {
    if (action === "retry") return render();
    if (action === "go-wardrobe") { state.page = "wardrobe"; return render(); }
    if (action === "go-plan") { state.page = "plan"; return render(); }
    if (action === "open-item") return openItemForm();
    if (action === "compose-outfit") return composeOutfit();
    if (action === "close-modal" || (action === "backdrop" && event.target === element)) {
      document.querySelector("#modal-root").innerHTML = "";
      return;
    }
    if (action === "edit-item") return openItemForm(await request(`/wardrobe/items/${element.dataset.id}`));
    if (action === "delete-item") {
      if (!window.confirm("Удалить вещь из гардероба?")) return;
      await deleteItem(element.dataset.id);
      document.querySelector("#modal-root").innerHTML = "";
      showToast("Вещь удалена");
      return render();
    }
    if (action === "laundry") {
      await changeLaundry(element.dataset.id, element.dataset.value === "true");
      showToast("Статус стирки обновлён");
      return render();
    }
    if (action === "select-outfit") {
      await request(`/outfits/${element.dataset.id}/select`, { method: "POST" });
      showToast("Образ добавлен в историю");
      return render();
    }
    if (action === "add-favorite") {
      await request("/favorites", { method: "POST", body: { outfitId: Number(element.dataset.id) } });
      showToast("Добавлено в избранное");
      return render();
    }
    if (action === "remove-favorite") {
      await request(`/favorites/${element.dataset.id}`, { method: "DELETE" });
      showToast("Удалено из избранного");
      return render();
    }
    if (action === "replace-item") {
      const select = document.querySelector(`#replace-${element.dataset.favorite}-${element.dataset.item}`);
      if (!select?.value) throw new Error("Выберите вещь для замены");
      await request(`/favorites/${element.dataset.favorite}/items/${element.dataset.item}`, {
        method: "PUT", body: { itemId: Number(select.value) }
      });
      showToast("Вещь в образе заменена");
      return render();
    }
    if (action === "rate") {
      await request(`/outfits/${element.dataset.id}/rating`, {
        method: "PUT", body: { score: Number(element.dataset.score) }
      });
      showToast("Спасибо за оценку!");
      return render();
    }
    if (action === "delete-account") {
      if (!window.confirm("Удалить аккаунт и все данные без возможности восстановления?")) return;
      await request("/account", { method: "DELETE" });
      await request("/account?confirm=true", { method: "DELETE" });
      clearSession();
      return render();
    }
    if (action === "subscribe-push") {
      await subscribePush();
      return;
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

document.addEventListener("click", async (event) => {
  const target = event.target instanceof Element ? event.target.closest("[data-page], [data-action], [data-filter], [data-settings-tab], [data-theme-set], .theme-toggle, .logout, .mobile-logout") : null;
  if (!target) return;
  if (target.matches("[data-page]")) {
    state.page = target.dataset.page;
    state.search = "";
    await render();
  } else if (target.matches("[data-action]")) {
    await handleAction(target, event);
  } else if (target.matches("[data-filter]")) {
    state.filter = target.dataset.filter;
    await render();
  } else if (target.matches("[data-settings-tab]")) {
    state.settingsTab = target.dataset.settingsTab;
    await render();
  } else if (target.matches("[data-theme-set]")) {
    try {
      await request("/settings/theme", { method: "PUT", body: { theme: target.dataset.themeSet } });
      state.theme = target.dataset.themeSet;
      localStorage.setItem(STORAGE_KEYS.theme, state.theme);
      await render();
    } catch (error) { showToast(error.message, true); }
  } else if (target.matches(".theme-toggle")) {
    try {
      const theme = state.theme === "DARK" ? "LIGHT" : "DARK";
      await request("/settings/theme", { method: "PUT", body: { theme } });
      state.theme = theme;
      localStorage.setItem(STORAGE_KEYS.theme, theme);
      await render();
    } catch (error) { showToast(error.message, true); }
  } else if (target.matches(".logout, .mobile-logout")) {
    await logout();
    clearSession();
    await render();
  }
});

document.addEventListener("input", async (event) => {
  if (event.target.id === "wardrobe-search") {
    state.search = event.target.value;
    const position = event.target.selectionStart;
    app.innerHTML = await renderWardrobe();
    const input = app.querySelector("#wardrobe-search");
    input.focus();
    input.setSelectionRange(position, position);
  }
  if (event.target.id === "vapid-public-key") {
    state.publicVapidKey = event.target.value.trim();
    localStorage.setItem(STORAGE_KEYS.vapid, state.publicVapidKey);
  }
});

document.addEventListener("change", (event) => {
  if (event.target.id === "item-photo") {
    const file = event.target.files[0];
    const label = document.querySelector("#file-label");
    if (label) label.textContent = file ? file.name : "Загрузить фото";
  }
  if (event.target.closest("#item-form")) {
    const errors = document.querySelector("#item-form-errors");
    if (errors) errors.textContent = "";
  }
});

document.addEventListener("input", (event) => {
  const itemForm = event.target.closest("#item-form");
  const formSelector = itemForm ? "#item-form-errors"
    : event.target.closest("#profile-form") ? "#profile-form-errors" : "";
  if (!formSelector) return;
  const errors = document.querySelector(formSelector);
  if (errors) errors.textContent = "";
  if (itemForm && event.target.name) {
    event.target.removeAttribute("aria-invalid");
    const fieldError = itemForm.querySelector(`#${event.target.id}-error`);
    if (fieldError) fieldError.textContent = "";
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.querySelector("#modal-root .modal-backdrop")) {
    document.querySelector("#modal-root").innerHTML = "";
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.id === "plan-form") await submitPlan(event, render);
  else if (event.target.id === "profile-form") await saveProfile(event, render);
  else if (event.target.id === "notification-form") await saveNotifications(event, render);
  else if (event.target.id === "compose-form") await saveComposedOutfit(event, render);
});

window.addEventListener("clima:item-saved", render);

window.addEventListener("clima:unauthorized", () => {
  clearSession();
  render();
});

render();

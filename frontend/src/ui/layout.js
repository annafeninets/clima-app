import { state } from "../core/state.js?v=20261008-02";
import { escapeHTML, icon } from "./helpers.js";

export const ROUTE_NAMES = {
  home: "Обзор", plan: "Образы", wardrobe: "Гардероб",
  favorites: "Избранное", history: "История", settings: "Настройки"
};

function navButton(page) {
  const symbols = { home: "home", plan: "sparkle", wardrobe: "hanger", favorites: "heart", history: "clock", settings: "settings" };
  return `<button class="nav-link ${state.page === page ? "active" : ""}" data-page="${page}" title="${ROUTE_NAMES[page]}" aria-label="${ROUTE_NAMES[page]}">${icon(symbols[page])}<span>${ROUTE_NAMES[page]}</span></button>`;
}

export function shell(content) {
  const dateText = new Intl.DateTimeFormat("ru-RU", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  return `<div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">${icon("sun")}</div><div><div class="brand-name">clima</div><div class="brand-caption">style by weather</div></div></div>
      <div class="nav-label">Меню</div><nav class="nav-list">${["home", "plan", "wardrobe", "favorites", "history", "settings"].map(navButton).join("")}</nav>
      <div class="sidebar-bottom"><div class="weather-note"><strong>Гардероб с умом</strong><p>Образы, которые подходят погоде и вашему стилю.</p></div>
        <div class="user-chip"><div class="avatar" title="${escapeHTML(state.login || "Пользователь")}">${escapeHTML((state.login[0] || "U").toUpperCase())}</div><div class="user-meta"><strong>${escapeHTML(state.login || "Пользователь")}</strong><span>Личный гардероб</span></div></div>
      </div>
    </aside>
    <main class="main"><header class="topbar"><div><div class="eyebrow">Ваш персональный стилист</div><div class="topbar-date">${escapeHTML(dateText)}</div></div><div class="top-actions"><button class="icon-button theme-toggle" title="Сменить тему">${icon("sun")}</button><button class="icon-button logout mobile-logout" title="Выйти">${icon("logout")}</button></div></header><div class="page">${content}</div></main>
    <nav class="mobile-nav">${["home", "plan", "wardrobe", "favorites", "settings"].map(navButton).join("")}</nav><div id="modal-root"></div>
  </div>`;
}

export function heading(title, subtitle, action = "") {
  return `<div class="page-heading"><div><h1>${title}</h1><p class="page-subtitle">${subtitle}</p></div>${action ? `<div class="heading-actions">${action}</div>` : ""}</div>`;
}

export function emptyState(title, description, buttonText = "", action = "") {
  return `<div class="card empty"><div class="empty-art">${icon("sparkle")}</div><h3>${title}</h3><p>${description}</p>${buttonText ? `<button class="button" data-action="${action}">${icon("plus")}${buttonText}</button>` : ""}</div>`;
}

export function loadingError(message) {
  return `<div class="card empty"><div class="empty-art">${icon("cloud")}</div><h3>${escapeHTML(message)}</h3><p>API: ${escapeHTML(state.api)}</p><button class="button" data-action="retry">Повторить</button></div>`;
}

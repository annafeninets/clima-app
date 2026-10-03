import { request } from "../core/api.js";
import { state, STORAGE_KEYS, saveSession } from "../core/state.js";
import { escapeHTML, icon, showToast } from "../ui/helpers.js";

export function renderAuth() {
  const register = state.authMode === "register";
  return `<div class="auth-screen"><section class="auth-visual"><div class="brand"><div class="brand-mark">${icon("sun")}</div><div><div class="brand-name">clima</div><div class="brand-caption">style by weather</div></div></div><div class="auth-message"><h1>Погода меняется.<br/>Стиль остаётся.</h1><p>Ваш личный гардероб, подобранные по погоде образы и немного больше уверенности каждое утро.</p></div><div class="auth-quote">Персональный стилист, который знает ваш гардероб.</div></section><section class="auth-form-side"><form id="auth-form" class="auth-form"><h2>${register ? "Создайте аккаунт" : "С возвращением"}</h2><p>${register ? "Начните собирать свой цифровой гардероб." : "Войдите, чтобы посмотреть ваш гардероб и образы."}</p><div class="field"><label for="auth-login">Email или телефон</label><input id="auth-login" name="login" type="text" autocomplete="username" required value="${escapeHTML(state.login)}" placeholder="you@example.com" /></div><div class="field"><label for="auth-password">Пароль</label><input id="auth-password" name="password" type="password" autocomplete="${register ? "new-password" : "current-password"}" minlength="8" required placeholder="Не менее 8 символов" /></div>${register ? `<div class="field"><label for="auth-confirm">Повторите пароль</label><input id="auth-confirm" name="confirm" type="password" autocomplete="new-password" minlength="8" required placeholder="Повторите пароль" /></div>` : ""}<div class="auth-error" id="auth-error"></div><button class="button" style="width:100%" type="submit">${register ? "Зарегистрироваться" : "Войти"} ${icon("arrow")}</button><div class="auth-switch">${register ? "Уже есть аккаунт?" : "Впервые в Clima?"} <button type="button" data-action="toggle-auth">${register ? "Войти" : "Создать аккаунт"}</button></div><div class="auth-api"><label for="api-url">Адрес backend API</label><input id="api-url" value="${escapeHTML(state.api)}" spellcheck="false" /></div></form></section></div>`;
}

export async function submitAuth(event, onSuccess) {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const errorNode = document.querySelector("#auth-error");
  const apiValue = document.querySelector("#api-url").value.trim().replace(/\/+$/, "");
  if (apiValue) {
    state.api = apiValue;
    localStorage.setItem(STORAGE_KEYS.api, apiValue);
  }
  const body = { login: String(data.get("login")).trim(), password: String(data.get("password")) };
  if (state.authMode === "register") {
    body.confirm = String(data.get("confirm"));
    if (body.password !== body.confirm) {
      errorNode.textContent = "Пароли не совпадают";
      return;
    }
  }
  try {
    const result = await request(`/auth/${state.authMode}`, { method: "POST", body });
    saveSession(result.token, body.login);
    state.page = "home";
    await onSuccess();
  } catch (error) {
    errorNode.textContent = error.message;
  }
}

export function toggleAuthMode() {
  state.authMode = state.authMode === "login" ? "register" : "login";
}

export async function logout() {
  try { await request("/auth/logout", { method: "POST" }); }
  catch (error) {
    if (!/сессия|авторизац|неверн/i.test(error.message)) showToast(error.message, true);
  }
}

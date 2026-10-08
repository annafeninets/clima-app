import { request } from "../core/api.js";
import { state, saveSession } from "../core/state.js?v=20261008-03";
import { escapeHTML, icon, showToast } from "../ui/helpers.js";

export function renderAuth() {
  const register = state.authMode === "register";
  return `<div class="auth-screen"><section class="auth-visual"><div class="brand"><div class="brand-mark">${icon("sun")}</div><div><div class="brand-name">clima</div><div class="brand-caption">style by weather</div></div></div><div class="auth-message"><h1>Погода меняется.<br/>Стиль остаётся.</h1><p>Ваш личный гардероб, подобранные по погоде образы и немного больше уверенности каждое утро.</p></div><div class="auth-quote">Персональный стилист, который знает ваш гардероб.</div></section><section class="auth-form-side"><form id="auth-form" class="auth-form" novalidate><h2>${register ? "Создайте аккаунт" : "С возвращением"}</h2><p>${register ? "Начните собирать свой цифровой гардероб." : "Войдите, чтобы посмотреть ваш гардероб и образы."}</p><div class="field"><label for="auth-login">Email или телефон</label><input id="auth-login" name="login" type="text" autocomplete="username" required value="${escapeHTML(state.login)}" placeholder="you@example.com" /></div><div class="field"><label for="auth-password">Пароль</label><input id="auth-password" name="password" type="password" autocomplete="${register ? "new-password" : "current-password"}" required placeholder="Не менее 8 символов" /></div>${register ? `<div class="field"><label for="auth-confirm">Повторите пароль</label><input id="auth-confirm" name="confirm" type="password" autocomplete="new-password" required placeholder="Повторите пароль" /></div>` : ""}<div class="auth-error" id="auth-error" role="alert" aria-live="polite"></div><button class="button" style="width:100%" type="submit">${register ? "Зарегистрироваться" : "Войти"} ${icon("arrow")}</button><div class="auth-switch">${register ? "Уже есть аккаунт?" : "Впервые в Clima?"} <button type="button" data-action="toggle-auth">${register ? "Войти" : "Создать аккаунт"}</button></div></form></section></div>`;
}

export async function submitAuth(event, onSuccess) {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const errorNode = document.querySelector("#auth-error");
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  const login = String(data.get("login") || "").trim();
  const password = String(data.get("password") || "");
  const confirm = String(data.get("confirm") || "");
  const validationMessage = !login
    ? "Введите email или номер телефона."
    : password.length < 8
      ? "Пароль должен содержать не менее 8 символов."
      : state.authMode === "register" && password !== confirm
        ? "Пароли не совпадают."
        : "";

  errorNode.textContent = "";
  if (validationMessage) {
    errorNode.textContent = validationMessage;
    document.querySelector(!login ? "#auth-login" : "#auth-password")?.focus();
    return;
  }

  const body = { login, password };
  if (state.authMode === "register") body.confirm = confirm;
  try {
    submitButton.disabled = true;
    const result = await request(`/auth/${state.authMode}`, { method: "POST", body });
    if (typeof result?.token !== "string" || !result.token) {
      throw new Error("Сервер не вернул токен входа. Попробуйте ещё раз.");
    }
    saveSession(result.token, body.login);
    state.page = "home";
    await onSuccess();
  } catch (error) {
    if (errorNode?.isConnected) {
      errorNode.textContent = error.message || "Не удалось войти. Проверьте логин и пароль.";
    }
  } finally { submitButton.disabled = false; }
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

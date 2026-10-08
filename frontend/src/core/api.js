import { state } from "./state.js?v=20261008-02";

export async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  let body = options.body;
  if (body !== undefined && !(body instanceof Blob) && !(body instanceof ArrayBuffer)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${state.api.replace(/\/+$/, "")}${path}`, { ...options, headers, body });
  } catch {
    throw new Error(`Не удалось подключиться к API ${state.api}. Проверьте, что backend запущен и CORS разрешает адрес frontend.`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    let message = `Ошибка сервера (${response.status})`;
    if (contentType.includes("json")) {
      try { message = (await response.json()).message || message; } catch { /* Keep the HTTP status message. */ }
    }
    if (response.status === 401 && state.token) {
      window.dispatchEvent(new Event("clima:unauthorized"));
    }
    throw new ApiError(message, response.status);
  }

  if (contentType.includes("application/json")) {
    const payload = await response.json();
    if (!payload.success) throw new ApiError(payload.message || "Не удалось выполнить запрос", response.status);
    return payload.data;
  }
  return response.blob();
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const photoCache = new Map();

export function photoUrl(photo) {
  if (!photo) return Promise.resolve("");
  if (/^data:image\//i.test(photo) || /^blob:/i.test(photo)) return Promise.resolve(photo);
  const path = photo.startsWith("/") ? photo : `/${photo}`;
  if (!photoCache.has(path)) {
    photoCache.set(path, request(path).then((blob) => URL.createObjectURL(blob)).catch(() => ""));
  }
  return photoCache.get(path);
}

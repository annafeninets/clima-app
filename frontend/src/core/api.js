import { state } from "./state.js?v=20261012-01";

export async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  let body = options.body;
  if (body !== undefined && !(body instanceof Blob) && !(body instanceof ArrayBuffer) && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${state.api}${path}`, {
      ...options, headers, body, signal: options.signal,
    });
  } catch (cause) {
    const error = new Error(
      `Не удалось подключиться к API ${state.api}. Проверьте, что backend запущен и CORS разрешает адрес frontend.`
    );
    error.cause = cause;
    throw error;
  }

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    let message = `Ошибка сервера (${response.status})`;
    if (contentType.includes("json")) {
      try { message = (await response.json()).message || message; } catch { /* keep status */ }
    }
    if (response.status === 401 && state.token) {
      window.dispatchEvent(new Event("clima:unauthorized"));
    }
    throw new ApiError(message, response.status);
  }

  if (contentType.includes("application/json")) {
    const payload = await response.json();
    if (payload && payload.success === false) {
      throw new ApiError(payload.message || "Не удалось выполнить запрос", response.status);
    }
    return payload && Object.hasOwn(payload, "data") ? payload.data : payload;
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
const MAX_PHOTO_CACHE_SIZE = 50;

export function photoUrl(photo) {
  if (!photo) return Promise.resolve("");
  if (/^data:image\//i.test(photo) || /^blob:/i.test(photo)) return Promise.resolve(photo);
  const path = photo.startsWith("/") ? photo : `/${photo}`;

  const cached = photoCache.get(path);
  if (cached) {
    cached.accessTime = Date.now();
    if (cached.url !== null) return Promise.resolve(cached.url);
    if (cached.promise !== null) return cached.promise;
  }

  let resolvePromise, rejectPromise;
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });

  const cacheEntry = { url: null, promise, accessTime: Date.now() };
  photoCache.set(path, cacheEntry);

  request(path)
    .then((blob) => {
      const blobURL = URL.createObjectURL(blob);
      photoCache.set(path, { url: blobURL, promise: null, accessTime: Date.now() });
      resolvePromise(blobURL);
    })
    .catch((error) => {
      photoCache.delete(path);
      rejectPromise(error);
    });

  if (photoCache.size > MAX_PHOTO_CACHE_SIZE) {
    let lruPath = null, lruTime = Infinity;
    for (const [cachePath, entry] of photoCache.entries()) {
      if (entry.accessTime < lruTime) { lruTime = entry.accessTime; lruPath = cachePath; }
    }
    if (lruPath !== null) {
      const lruEntry = photoCache.get(lruPath);
      if (lruEntry?.url) {
        try { URL.revokeObjectURL(lruEntry.url); } catch { /* ignore */ }
      }
      photoCache.delete(lruPath);
    }
  }

  return promise;
}

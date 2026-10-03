export const STORAGE_KEYS = {
  token: "clima.token",
  login: "clima.login",
  theme: "clima.theme",
  vapid: "clima.vapid"
};

export const SEASONS = ["WINTER", "SPRING", "SUMMER", "AUTUMN"];
export const SEASON_LABELS = { WINTER: "Зима", SPRING: "Весна", SUMMER: "Лето", AUTUMN: "Осень" };
export const PARTS = {
  TOP: "Верх",
  BOTTOM: "Низ",
  SHOES: "Обувь",
  ACCESSORY: "Аксессуары",
  ONE_PIECE: "Платье / комбинезон"
};

export const state = {
  api: (window.CLIMA_CONFIG?.apiBaseUrl || "http://127.0.0.1:8000").replace(/\/+$/, ""),
  token: localStorage.getItem(STORAGE_KEYS.token) || "",
  login: localStorage.getItem(STORAGE_KEYS.login) || "",
  theme: localStorage.getItem(STORAGE_KEYS.theme) || "LIGHT",
  publicVapidKey: localStorage.getItem(STORAGE_KEYS.vapid) || window.CLIMA_CONFIG?.vapidPublicKey || "",
  page: "home",
  outfits: [],
  wardrobe: [],
  favorites: [],
  history: [],
  profile: {},
  settings: {},
  location: "",
  filter: "ALL",
  search: "",
  settingsTab: "profile",
  authMode: "login",
  homeError: ""
};

export function clearSession() {
  state.token = "";
  state.login = "";
  localStorage.removeItem(STORAGE_KEYS.token);
  localStorage.removeItem(STORAGE_KEYS.login);
}

export function saveSession(token, login) {
  state.token = token;
  state.login = login;
  localStorage.setItem(STORAGE_KEYS.token, token);
  localStorage.setItem(STORAGE_KEYS.login, login);
}

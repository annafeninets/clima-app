export const STORAGE_KEYS = {
  token: "clima.token",
  login: "clima.login",
  theme: "clima.theme",
  vapid: "clima.vapid",
  timeZone: "clima.timeZone"
};

export const SEASONS = ["WINTER", "SPRING", "SUMMER", "AUTUMN"];
export const SEASON_LABELS = { WINTER: "Зима", SPRING: "Весна", SUMMER: "Лето", AUTUMN: "Осень" };
export const PARTS = {
  TOP: "Верх",
  BOTTOM: "Низ",
  SHOES: "Обувь",
  OUTERWEAR: "Верхняя одежда",
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
  planDate: "",
  filter: "ALL",
  search: "",
  settingsTab: "profile",
  authMode: "login",
  homeError: ""
};

const missingFromUrl = new URLSearchParams(window.location.search).get("missing");
const wardrobeHintCategories = new Set([
  "top", "outerwear", "bottom", "shoes", "bag", "hat", "accessories"
]);
state.wardrobeHintMissing = missingFromUrl
  ? missingFromUrl.split(",").filter((category) => wardrobeHintCategories.has(category))
  : [];
if (state.wardrobeHintMissing.length) state.page = "wardrobe";

export function clearSession() {
  state.token = "";
  state.login = "";
  localStorage.removeItem(STORAGE_KEYS.token);
  localStorage.removeItem(STORAGE_KEYS.login);
  localStorage.removeItem(STORAGE_KEYS.timeZone);
}

export function saveSession(token, login) {
  state.token = token;
  state.login = login;
  localStorage.setItem(STORAGE_KEYS.token, token);
  localStorage.setItem(STORAGE_KEYS.login, login);
}

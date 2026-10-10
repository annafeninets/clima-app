// Страна пользователя без хардкода списка городов:
// 1) сохранённая настройка / выбранный город
// 2) IANA timeZone → ISO-код
// 3) navigator.language
// 4) пустая строка → вызывающий код показывает топ мировых городов

const STORAGE_KEY = "clima.country";

const TZ_COUNTRY = {
  "Europe/Moscow": "RU", "Europe/Kaliningrad": "RU", "Europe/Samara": "RU",
  "Europe/Volgograd": "RU", "Europe/Saratov": "RU", "Europe/Ulyanovsk": "RU",
  "Europe/Astrakhan": "RU", "Europe/Kirov": "RU", "Asia/Yekaterinburg": "RU",
  "Asia/Omsk": "RU", "Asia/Novosibirsk": "RU", "Asia/Barnaul": "RU",
  "Asia/Tomsk": "RU", "Asia/Novokuznetsk": "RU", "Asia/Krasnoyarsk": "RU",
  "Asia/Irkutsk": "RU", "Asia/Chita": "RU", "Asia/Yakutsk": "RU",
  "Asia/Vladivostok": "RU", "Asia/Magadan": "RU", "Asia/Sakhalin": "RU",
  "Asia/Kamchatka": "RU", "Asia/Anadyr": "RU",
  "Europe/Minsk": "BY", "Europe/Kiev": "UA", "Europe/Kyiv": "UA",
  "Europe/London": "GB", "Europe/Paris": "FR", "Europe/Berlin": "DE",
  "Europe/Madrid": "ES", "Europe/Rome": "IT", "Europe/Amsterdam": "NL",
  "Europe/Warsaw": "PL", "Europe/Prague": "CZ", "Europe/Vienna": "AT",
  "Europe/Stockholm": "SE", "Europe/Oslo": "NO", "Europe/Copenhagen": "DK",
  "Europe/Helsinki": "FI", "Europe/Athens": "GR", "Europe/Istanbul": "TR",
  "Europe/Lisbon": "PT", "Europe/Brussels": "BE", "Europe/Zurich": "CH",
  "Europe/Dublin": "IE", "Europe/Bucharest": "RO", "Europe/Budapest": "HU",
  "Europe/Sofia": "BG", "Europe/Riga": "LV", "Europe/Tallinn": "EE",
  "Europe/Vilnius": "LT", "Asia/Almaty": "KZ", "Asia/Tbilisi": "GE",
  "Asia/Yerevan": "AM", "Asia/Baku": "AZ", "Asia/Tashkent": "UZ",
  "Asia/Tokyo": "JP", "Asia/Shanghai": "CN", "Asia/Hong_Kong": "HK",
  "Asia/Seoul": "KR", "Asia/Singapore": "SG", "Asia/Bangkok": "TH",
  "Asia/Dubai": "AE", "Asia/Kolkata": "IN", "Asia/Jerusalem": "IL",
  "America/New_York": "US", "America/Chicago": "US", "America/Denver": "US",
  "America/Los_Angeles": "US", "America/Phoenix": "US", "America/Anchorage": "US",
  "Pacific/Honolulu": "US", "America/Toronto": "CA", "America/Vancouver": "CA",
  "America/Sao_Paulo": "BR", "America/Mexico_City": "MX",
  "America/Argentina/Buenos_Aires": "AR", "Australia/Sydney": "AU",
  "Australia/Melbourne": "AU", "Pacific/Auckland": "NZ",
  "Africa/Cairo": "EG", "Africa/Johannesburg": "ZA",
};

let cachedCountryCode = null;

function extractCountryFromLocale(locale) {
  if (!locale) return null;
  const match = String(locale).match(/[_-]([A-Za-z]{2})$/);
  return match ? match[1].toUpperCase() : null;
}

function countryFromTimeZone() {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && TZ_COUNTRY[tz]) return TZ_COUNTRY[tz];
    if (tz?.startsWith("America/")) return null;
  } catch {
    /* ignore */
  }
  return null;
}

function countryFromNavigator() {
  if (typeof navigator === "undefined") return null;
  const languages = [navigator.language, ...(navigator.languages || [])];
  for (const lang of languages) {
    const code = extractCountryFromLocale(lang);
    if (code) return code;
  }
  return null;
}

export function setUserCountry(code) {
  if (!code) return;
  cachedCountryCode = code.toUpperCase();
  try {
    localStorage.setItem(STORAGE_KEY, cachedCountryCode);
  } catch {
    /* ignore */
  }
}

export function useUserCountry() {
  if (cachedCountryCode) return cachedCountryCode;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      cachedCountryCode = stored.toUpperCase();
      return cachedCountryCode;
    }
  } catch {
    /* ignore */
  }
  const detected = countryFromTimeZone() || countryFromNavigator();
  cachedCountryCode = detected || "";
  return cachedCountryCode;
}

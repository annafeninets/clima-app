// Hook to determine the user's country code (ISO 3166-1 alpha-2)
// Priority:
// 1. Value saved in localStorage (key: 'clima.country') – set when user selects a country in settings or from profile.
// 2. Detected from browser language/locale (navigator.language, navigator.languages)
// 3. Fallback to default 'RU' (Russia) if detection fails.

let cachedCountryCode = null;

/**
 * Extracts a 2-letter country code from a locale string like 'en-US', 'ru-RU', 'fr-FR'.
 * Returns uppercase code or null if not found.
 */
function extractCountryFromLocale(locale) {
  if (!locale) return null;
  // Match patterns like xx-XX or xx_XX or xx (we take the part after separator if it's 2 letters and uppercase)
  const match = locale.match(/[_-]([A-Z]{2})$/);
  if (match) return match[1];
  // Some locales are just language code (like 'en') – we cannot infer country.
  return null;
}

/**
 * Tries to get country from navigator.language or navigator.languages.
 * @returns {string|null}
 */
function getCountryFromNavigator() {
  if (typeof navigator === 'undefined') return null;
  const languages = [];
  if (navigator.language) languages.push(navigator.language);
  if (navigator.languages) languages.push(...navigator.languages);
  for (const lang of languages) {
    const code = extractCountryFromLocale(lang);
    if (code) return code;
  }
  return null;
}

/**
 * Gets country code from localStorage if available.
 * @returns {string|null}
 */
function getCountryFromStorage() {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem('clima.country');
}

/**
 * Saves country code to localStorage.
 * @param {string} code
 */
export function setUserCountry(code) {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('clima.country', code.toUpperCase());
    cachedCountryCode = code.toUpperCase(); // update cache
  }
}

/**
 * Returns the user's country code (string, e.g., 'RU', 'US', 'FR').
 * Uses cached value if available to avoid repeated work.
 * @returns {string}
 */
export function useUserCountry() {
  if (cachedCountryCode !== null) {
    return cachedCountryCode;
  }

  // 1. Check localStorage
  const stored = getCountryFromStorage();
  if (stored) {
    cachedCountryCode = stored.toUpperCase();
    return cachedCountryCode;
  }

  // 2. Try to detect from browser locale
  const detected = getCountryFromNavigator();
  if (detected) {
    cachedCountryCode = detected.toUpperCase();
    return cachedCountryCode;
  }

  // 3. Fallback to default
  cachedCountryCode = 'RU';
  return cachedCountryCode;
}
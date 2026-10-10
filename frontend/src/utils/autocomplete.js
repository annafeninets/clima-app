// Общий компонент автокомплита: debounce, AbortController, кэш на стороне
// браузера (HTTP cache), клавиатурная навигация и a11y (role=combobox).
//
// Три публичных входа:
//   mountCombobox(input, { load, onSelect, debounceMs })  — низкоуровневый
//   initAutocomplete(input, { seed })                     — обёртка для городов
//   mountStaticCombobox(input, values, onSelect)          — статический список
//
// initAutocomplete ходит в backend (см. clima/handlers/command.py):
//   GET /places/context          → подсказки по IP (пустой фокус)
//   GET /places/search?q=...     → fuzzy-поиск при вводе
// Оба пути требуют Authorization: Bearer <token> — токен берётся из state.js.

import { escapeHTML } from "../ui/helpers.js";
import { state, STORAGE_KEYS, setPlace } from "../core/state.js?v=20261008-03";

export function debounce(fn, delay) {
  let timeoutId = 0;
  const wrapped = (...args) => {
    clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => fn(...args), delay);
  };
  wrapped.cancel = () => clearTimeout(timeoutId);
  return wrapped;
}

export function ensureCombobox(input) {
  const field = input.closest(".field") || input.parentElement;
  let wrapper = input.closest(".autocomplete");
  if (!wrapper) {
    wrapper = document.createElement("div");
    wrapper.className = "autocomplete";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
  }
  let list = wrapper.querySelector(".autocomplete-list");
  if (!list) {
    list = document.createElement("div");
    list.className = "autocomplete-list";
    list.id = `${input.id || "field"}-suggestions`;
    list.setAttribute("role", "listbox");
    list.hidden = true;
    wrapper.appendChild(list);
  }
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", list.id);
  input.setAttribute("autocomplete", "off");
  if (field && !wrapper.contains(list)) field.appendChild(list);
  return list;
}

/**
 * Общий combobox: список при фокусе, фильтр по вводу, клавиатура, a11y.
 * @param {HTMLInputElement} input
 * @param {{
 *   load: (query: string, ctx: { signal: AbortSignal, empty: boolean })
 *     => Promise<Array<{title:string, subtitle?:string, value?:string, meta?:any}>>,
 *   onSelect?: (item: any, row: any) => void,
 *   debounceMs?: number,
 * }} options
 */
export function mountCombobox(input, options) {
  if (!input) return { destroy() {} };
  const list = ensureCombobox(input);
  const debounceMs = options.debounceMs ?? 250;
  let activeIndex = -1;
  let items = [];
  let controller = null;
  let requestId = 0;

  const close = () => {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activeIndex = -1;
  };

  const render = (rows, { loading = false, emptyQuery = false } = {}) => {
    items = rows;
    if (loading) {
      list.innerHTML = `<div class="autocomplete-status" role="status">Загрузка…</div>`;
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      return;
    }
    if (!rows.length) {
      list.innerHTML = `<div class="autocomplete-status" role="status">${emptyQuery ? "Нет подсказок" : "Ничего не найдено"}</div>`;
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      return;
    }
    activeIndex = -1;
    list.innerHTML = rows.map((row, index) => {
      const subtitle = row.subtitle
        ? `<span class="autocomplete-option-subtitle">${escapeHTML(row.subtitle)}</span>`
        : "";
      return `<button class="autocomplete-option" type="button" role="option" id="${list.id}-option-${index}" aria-selected="false" data-index="${index}"><span class="autocomplete-option-title">${escapeHTML(row.title)}</span>${subtitle}</button>`;
    }).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };

  const choose = (row) => {
    input.value = row.value ?? row.title;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    options.onSelect?.(row.meta ?? row, row);
    close();
  };

  const loadSuggestions = async (query, empty) => {
    controller?.abort();
    controller = new AbortController();
    const current = ++requestId;
    render([], { loading: true });
    try {
      const rows = await options.load(query, { signal: controller.signal, empty });
      if (current !== requestId) return;
      render(rows || [], { emptyQuery: empty });
    } catch (error) {
      if (error?.name === "AbortError" || current !== requestId) return;
      render([], { emptyQuery: empty });
    }
  };

  const debouncedLoad = debounce((query) => loadSuggestions(query, false), debounceMs);

  const onFocus = () => {
    const query = input.value.trim();
    loadSuggestions(query, query.length === 0);
  };
  const onInput = () => {
    const query = input.value.trim();
    if (!query) loadSuggestions("", true);
    else debouncedLoad(query);
  };
  const onBlur = () => window.setTimeout(close, 140);
  const onKeydown = (event) => {
    const optionsEls = [...list.querySelectorAll('[role="option"]')];
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (!optionsEls.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex =
        (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + optionsEls.length) %
        optionsEls.length;
      optionsEls.forEach((option, index) => {
        option.setAttribute("aria-selected", String(index === activeIndex));
      });
      input.setAttribute("aria-activedescendant", optionsEls[activeIndex].id);
      optionsEls[activeIndex].scrollIntoView({ block: "nearest" });
      return;
    }
    if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      choose(items[activeIndex]);
    }
  };

  input.addEventListener("focus", onFocus);
  input.addEventListener("input", onInput);
  input.addEventListener("blur", onBlur);
  input.addEventListener("keydown", onKeydown);
  list.addEventListener("mousedown", (event) => event.preventDefault());
  list.addEventListener("click", (event) => {
    const option = event.target.closest("[data-index]");
    if (!option) return;
    choose(items[Number(option.dataset.index)]);
  });

  return {
    destroy() {
      debouncedLoad.cancel?.();
      controller?.abort();
      input.removeEventListener("focus", onFocus);
      input.removeEventListener("input", onInput);
      input.removeEventListener("blur", onBlur);
      input.removeEventListener("keydown", onKeydown);
    },
  };
}

// Статический combobox: фильтрует локальный массив values, без сети.
export function mountStaticCombobox(input, values, onSelect) {
  const normalized = values.map((value) =>
    typeof value === "string" ? { title: value, value } : value
  );
  return mountCombobox(input, {
    debounceMs: 0,
    async load(query) {
      const q = query.trim().toLowerCase();
      const rows = q
        ? normalized.filter(
            (row) =>
              row.title.toLowerCase().includes(q) ||
              String(row.value || "").toLowerCase().includes(q)
          )
        : normalized;
      return rows.slice(0, 40);
    },
    onSelect,
  });
}

// ---------------------------------------------------------------------------
// initAutocomplete — фасад для полей «Город/место».
//
// Контракт с app.js: initAutocomplete(input, { seed: state.location }).
// При выборе:
//   1) input.dataset.lat/lon ← координаты (использует outfits.js#submitPlan);
//   2) setPlace(place) — пишет state.selectedPlace + localStorage;
//   3) window.dispatchEvent("clima:place-selected", { detail: place })
//      — для синхронизации вкладок, слушается в app.js.
// ---------------------------------------------------------------------------

function authHeaders() {
  const headers = { Accept: "application/json" };
  const token = state.token || localStorage.getItem(STORAGE_KEYS.token);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

// Backend заворачивает ответы в { success, message, data }.
// Разворачиваем — сначала пробуем data.data, потом сам data.
function extractPlaces(data) {
  const payload = data?.data ?? data;
  if (Array.isArray(payload)) return payload;
  return payload?.suggestions || payload?.places || payload?.items || [];
}

export function initAutocomplete(input, options = {}) {
  if (!input) return { destroy() {} };

  if (options.seed && !input.value.trim()) {
    input.value = options.seed;
  }

  const combobox = mountCombobox(input, {
    debounceMs: 250,

    async load(query, { signal, empty }) {
      const path = empty
        ? "/places/context"
        : `/places/search?q=${encodeURIComponent(query)}&limit=20`;

      const res = await fetch(path, { signal, headers: authHeaders() });
      if (!res.ok) return [];
      const data = await res.json();
      return extractPlaces(data).map((place) => ({
        title: place.name || place.label || "",
        subtitle: place.region || place.country || "",
        value: place.name || "",
        meta: place,
      }));
    },

    onSelect(row) {
      const place = row?.meta ?? row;
      if (!place?.name) return;

      // 1) координаты — на input, чтобы submitPlan их прочитал
      input.dataset.lat = place.lat ?? "";
      input.dataset.lon = place.lon ?? "";

      // 2) сохраняем в общий стейт + localStorage
      setPlace(place);

      // 3) событие — для слушателей в app.js
      window.dispatchEvent(new CustomEvent("clima:place-selected", { detail: place }));
    },
  });

  return {
    destroy() {
      try {
        combobox?.destroy?.();
      } catch {
        /* noop */
      }
    },
  };
}

export function initStaticAutocomplete(input, values, onSelect) {
  return mountStaticCombobox(input, values, onSelect);
}
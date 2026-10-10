import { useUserCountry } from "../hooks/useUserCountry.js";
import { fetchPlaces, resolveUserCountry } from "../services/placeSearch.js";
import { escapeHTML } from "../ui/helpers.js";

function debounce(fn, delay) {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

function placeLabel(place) {
  const parts = [place.region, place.country].filter(Boolean);
  return parts.length ? parts.join(", ") : place.countryCode || "";
}

function ensureList(input) {
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
    list.id = `${input.id || "place"}-suggestions`;
    list.setAttribute("role", "listbox");
    list.hidden = true;
    wrapper.appendChild(list);
  }
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", list.id);
  input.setAttribute("autocomplete", "off");
  return list;
}

/**
 * @param {HTMLInputElement} input
 * @param {{ seed?: string }} [options]
 */
export function initAutocomplete(input, options = {}) {
  if (!input || !(input instanceof HTMLInputElement)) return;

  const list = ensureList(input);
  let activeIndex = -1;
  let requestId = 0;
  let countryCode = useUserCountry();
  resolveUserCountry().then((code) => { countryCode = code; });

  const close = () => {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activeIndex = -1;
  };

  const render = (places) => {
    if (!places.length) {
      close();
      return;
    }
    activeIndex = -1;
    list.innerHTML = places.map((place, index) => {
      const subtitle = placeLabel(place);
      return `<button class="autocomplete-option" type="button" role="option" id="${list.id}-option-${index}" aria-selected="false" data-suggestion="${escapeHTML(place.name)}"><span class="autocomplete-option-title">${escapeHTML(place.name)}</span>${subtitle ? `<span class="autocomplete-option-subtitle">${escapeHTML(subtitle)}</span>` : ""}</button>`;
    }).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };

  const choose = (value) => {
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    close();
  };

  const loadSuggestions = async (query, showDefaults = false) => {
    const current = ++requestId;
    const seed = options.seed || input.defaultValue || input.getAttribute("value") || "";
    try {
      const places = await fetchPlaces({
        query,
        country: countryCode,
        seed: showDefaults && !query.trim() ? seed : "",
        limit: showDefaults && !query.trim() ? 15 : 10,
      });
      if (current !== requestId) return;
      render(places);
    } catch (error) {
      if (current !== requestId) return;
      console.error("Place autocomplete failed:", error);
      close();
    }
  };

  const debouncedLoad = debounce((query) => loadSuggestions(query, false), 250);

  input.addEventListener("focus", () => {
    const query = input.value.trim();
    if (query.length < 2) loadSuggestions("", true);
    else debouncedLoad(query);
  });

  input.addEventListener("input", () => {
    const query = input.value.trim();
    if (query.length < 2) loadSuggestions("", true);
    else debouncedLoad(query);
  });

  input.addEventListener("blur", () => window.setTimeout(close, 120));

  input.addEventListener("keydown", (event) => {
    const options = [...list.querySelectorAll('[role="option"]')];
    if (event.key === "Escape") {
      close();
      return;
    }
    if (!options.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options.forEach((option, index) => {
        option.setAttribute("aria-selected", String(index === activeIndex));
      });
      input.setAttribute("aria-activedescendant", options[activeIndex].id);
      return;
    }
    if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      choose(options[activeIndex].dataset.suggestion);
    }
  });

  list.addEventListener("mousedown", (event) => event.preventDefault());
  list.addEventListener("click", (event) => {
    const option = event.target.closest("[data-suggestion]");
    if (option) choose(option.dataset.suggestion);
  });
}

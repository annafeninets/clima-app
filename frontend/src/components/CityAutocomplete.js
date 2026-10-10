// CityAutocomplete.js
// A reusable autocomplete component for city selection.

import { searchCities, getDefaultCitiesByCountry } from '../services/citySearch.js';
import { useUserCountry } from '../hooks/useUserCountry.js';
import { toLatin, toCyrillic } from '../utils/transliteration.js';
import { levenshtein } from '../utils/levenshtein.js';

/**
 * @typedef {Object} CityAutocompleteOptions
 * @property {string} value - The current value of the input (city name string).
 * @property {(city: Object) => void} onChange - Callback when a city is selected.
 * @property {string} [defaultCountry] - ISO country code for default list when input is empty and focused.
 * @property {string} [placeholder] - Placeholder text for the input.
 * @property {number} [minChars=1] - Minimum characters to trigger search.
 * @property {number} [debounceMs=250] - Debounce time for search in milliseconds.
 */

export class CityAutocomplete {
  /**
   * @param {HTMLInputElement} input - The input element to enhance.
   * @param {CityAutocompleteOptions} options - Configuration options.
   */
  constructor(input, options = {}) {
    if (!(input instanceof HTMLInputElement)) {
      throw new Error('CityAutocomplete: first argument must be an HTMLInputElement');
    }

    this.input = input;
    this.value = options.value || '';
    this.onChange = options.onChange || (() => {});
    this.defaultCountry = options.defaultCountry || useUserCountry();
    this.placeholder = options.placeholder || '';
    this.minChars = options.minChars !== undefined ? options.minChars : 1;
    this.debounceMs = options.debounceMs !== undefined ? options.debounceMs : 250;

    // Internal state
    this.query = '';
    this.suggestions = [];
    this.activeIndex = -1; // index of highlighted suggestion in dropdown
    this.loading = false;
    this.dropdownVisible = false;
    this.debounceTimer = null;

    // Bind event listeners
    this._onInput = this._onInput.bind(this);
    this._onKeydown = this._onKeydown.bind(this);
    this._onFocus = this._onFocus.bind(this);
    this._onBlur = this._onBlur.bind(this);
    this._onClickOutside = this._onClickOutside.bind(this);

    // Initialize
    this._init();
  }

  /** Initialize the component: set attributes, event listeners, and placeholder. */
  _init() {
    // Set placeholder if provided
    if (this.placeholder) {
      this.input.placeholder = this.placeholder;
    }

    // Set initial value
    this.input.value = this.value;

    // Add ARIA attributes for combobox
    this.input.setAttribute('role', 'combobox');
    this.input.setAttribute('aria-autocomplete', 'list');
    this.input.setAttribute('aria-expanded', 'false');
    // aria-activedescendant will be set when dropdown is visible

    // Event listeners
    this.input.addEventListener('input', this._onInput);
    this.input.addEventListener('keydown', this._onKeydown);
    this.input.addEventListener('focus', this._onFocus);
    this.input.addEventListener('blur', this._onBlur);

    // Click outside listener on document
    document.addEventListener('click', this._onClickOutside);
  }

  /** Destroy the component: remove event listeners and dropdown. */
  destroy() {
    this.input.removeEventListener('input', this._onInput);
    this.input.removeEventListener('keydown', this._onKeydown);
    this.input.removeEventListener('focus', this._onFocus);
    this.input.removeEventListener('blur', this._onBlur);
    document.removeEventListener('click', this._onClickOutside);

    this._removeDropdown();
  }

  /* ================================== Event Handlers ================================== */

  _onInput() {
    this.query = this.input.value.trim();
    this.value = this.query; // keep in sync
    this.activeIndex = -1; // reset highlight

    if (this.query.length >= this.minChars) {
      this._startSearch();
    } else {
      // If query becomes less than minChars, hide dropdown unless it's empty and focused (handled in focus)
      if (this.query.length === 0 && this.input === document.activeElement) {
        this._showDefaultList();
      } else {
        this._hideDropdown();
      }
    }
  }

  _onKeydown(event) {
    const { key } = event;

    if (!this.dropdownVisible) {
      // If dropdown not visible, only special keys that might show it: Down arrow (to show first suggestion) or maybe Enter? We'll let Down arrow show dropdown with current query or default.
      if (key === 'ArrowDown') {
        event.preventDefault();
        if (this.query.length >= this.minChars) {
          this._startSearch(); // will show dropdown after search
        } else {
          this._showDefaultList(); // show default list for empty input
        }
        return;
      }
      // For other keys, do nothing
      return;
    }

    // Dropdown is visible
    switch (key) {
      case 'ArrowDown':
        event.preventDefault();
        this._moveHighlight(1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this._moveHighlight(-1);
        break;
      case 'Enter':
        event.preventDefault();
        if (this.activeIndex >= 0 && this.activeIndex < this.suggestions.length) {
          this._selectSuggestion(this.suggestions[this.activeIndex]);
        }
        break;
      case 'Escape':
        event.preventDefault();
        this._hideDropdown();
        this.input.blur(); // optionally blur on escape
        break;
      default:
        // Let other keys pass through to input
        break;
    }
  }

  _onFocus() {
    // When input gets focus, if query is empty, show default list for the country
    if (this.query.length === 0) {
      this._showDefaultList();
    }
    // Ensure ARIA expanded is true if dropdown is about to be shown
    this._updateARIAExpanded();
  }

  _onBlur() {
    // Hide dropdown after a short delay to allow click on suggestion to register
    setTimeout(() => {
      if (!this.dropdownVisible) return; // might have been shown again by mousedown on suggestion?
      this._hideDropdown();
    }, 200);
  }

  _onClickOutside(event) {
    // If the click is outside the input and outside the dropdown, hide dropdown
    if (this.input.contains(event.target)) return;
    if (this.dropdownElement && this.dropdownElement.contains(event.target)) return;
    this._hideDropdown();
  }

  /* ================================== Suggestion Logic ================================== */

  _startSearch() {
    if (this.loading) return;
    this.loading = true;
    this._updateARIAExpanded(true); // indicate loading

    // Clear existing debounce timer
    if (this.debounceTimer !== null) {
      clearTimeout(this.debounceTimer);
    }

    // Set debounce timer
    this.debounceTimer = setTimeout(() => {
      this._performSearch();
    }, this.debounceMs);
  }

  _performSearch() {
    this.loading = false;
    const query = this.query;

    // Use the citySearch service to get suggestions
    try {
      this.suggestions = searchCities(query, 10); // limit to 10 for now
      this.activeIndex = -1; // reset highlight
      this._updateDropdown();
    } catch (err) {
      console.error('CityAutocomplete search error:', err);
      this.suggestions = [];
      this._updateDropdown();
    }

    this.debounceTimer = null;
  }

  _showDefaultList() {
    // Show top cities of the user's country when input is empty and focused
    this.loading = true;
    this._updateARIAExpanded(true);

    // We'll get default cities for the defaultCountry
    try {
      this.suggestions = getDefaultCitiesByCountry(this.defaultCountry);
      // Limit to top 50 as per requirement, but our dataset may be smaller.
      // We'll sort by name and take first 50.
      this.suggestions = this.suggestions
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
        .slice(0, 50);
      this.activeIndex = -1;
      this._updateDropdown();
    } catch (err) {
      console.error('CityAutocomplete default list error:', err);
      this.suggestions = [];
      this._updateDropdown();
    }

    this.loading = false;
  }

  /* ================================== Dropdown Rendering ================================== */

  _updateDropdown() {
    if (!this.dropdownVisible && this.suggestions.length === 0) {
      return;
    }

    // Show dropdown if we have suggestions or if we are in loading/default state (even if empty? we'll show placeholder)
    this.dropdownVisible = this.suggestions.length > 0 || this.loading;

    if (this.dropdownVisible) {
      this._ensureDropdownElement();
      this._renderDropdownContent();
      this._positionDropdown();
      this._updateARIAExpanded(true);
    } else {
      this._removeDropdown();
      this._updateARIAExpanded(false);
    }
  }

  _ensureDropdownElement() {
    if (this.dropdownElement) return;

    this.dropdownElement = document.createElement('div');
    this.dropdownElement.className = 'city-autocomplete-dropdown';
    this.dropdownElement.setAttribute('role', 'listbox');
    this.dropdownElement.setAttribute('aria-label', 'Список предложений городов');
    // We'll append to body and position absolutely
    document.body.appendChild(this.dropdownElement);
  }

  _removeDropdown() {
    if (!this.dropdownElement) return;
    this.dropdownElement.remove();
    this.dropdownElement = null;
  }

  _renderDropdownContent() {
    if (!this.dropdownElement) return;

    // Clear current content
    this.dropdownElement.innerHTML = '';

    if (this.loading) {
      const loadingDiv = document.createElement('div');
      loadingDiv.className = 'city-autocomplete-loading';
      loadingDiv.textContent = 'Загрузка…';
      this.dropdownElement.appendChild(loadingDiv);
      return;
    }

    if (this.suggestions.length === 0) {
      const noResultsDiv = document.createElement('div');
      noResultsDiv.className = 'city-autocomplete-no-results';
      noResultsDiv.textContent = 'Ничего не найдено. Проверьте написание.';
      noResultsDiv.setAttribute('role', 'presentation'); // or maybe we want it to be announced? We'll use aria-live via input?
      this.dropdownElement.appendChild(noResultsDiv);
      return;
    }

    // Create suggestion items
    this.suggestions.forEach((city, index) => {
      const item = document.createElement('div');
      item.className = `city-autocomplete-item${index === this.activeIndex ? ' city-autocomplete-item-active' : ''}`;
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', index === this.activeIndex ? 'true' : 'false');
      // We'll store the city object in the element's dataset for easy access on click
      item.dataset.cityIndex = String(index);

      // Format the city name and region/country
      const name = document.createElement('div');
      name.className = 'city-autocomplete-name';
      name.textContent = city.name;

      const subtitle = document.createElement('div');
      subtitle.className = 'city-autocomplete-subtitle';
      subtitle.textContent = `${city.region}, ${city.country}`;

      item.appendChild(name);
      item.appendChild(subtitle);

      // Click to select
      item.addEventListener('mousedown', (e) => {
        // Prevent blur from hiding dropdown before we can select
        e.preventDefault();
        this._selectSuggestion(city);
      });

      this.dropdownElement.appendChild(item);
    });
  }

  _positionDropdown() {
    if (!this.dropdownElement) return;

    const rect = this.input.getBoundingClientRect();
    const top = rect.bottom + window.scrollY;
    const left = rect.left + window.scrollX;
    const width = rect.width;

    this.dropdownElement.style.top = `${top}px`;
    this.dropdownElement.style.left = `${left}px`;
    this.dropdownElement.style.width = `${width}px`;
    // Optional: set max-height and overflow-y for scrolling
    this.dropdownElement.style.maxHeight = '250px';
    this.dropdownElement.style.overflowY = 'auto';
  }

  _updateARIAExpanded(expanded) {
    this.input.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    // When expanded, we need to set aria-activedescendant to the id of the active option
    if (expanded && this.activeIndex >= 0 && this.dropdownElement) {
      // We could set an id on each option, but for simplicity we'll rely on aria-activedescendant being the id of the active option.
      // We'll generate an id based on the input id and index.
      const optionId = `${this.input.id}-option-${this.activeIndex}`;
      // Find the option element and set its id
      const option = this.dropdownElement.querySelector(`[data-city-index="${this.activeIndex}"]`);
      if (option) {
        option.id = optionId;
        this.input.setAttribute('aria-activedescendant', optionId);
      } else {
        this.input.removeAttribute('aria-activedescendant');
      }
    } else {
      this.input.removeAttribute('aria-activedescendant');
    }
  }

  /* ================================== Highlighting and Selection ================================== */

  _moveHighlight(delta) {
    if (this.suggestions.length === 0) return;
    let newIndex = this.activeIndex + delta;
    if (newIndex < 0) newIndex = this.suggestions.length - 1;
    if (newIndex >= this.suggestions.length) newIndex = 0;
    this.activeIndex = newIndex;
    this._updateDropdownContent(); // re-render to update active class
    this._updateARIAExpanded(true); // update aria-activedescendant
  }

  _selectSuggestion(city) {
    // Update input value to the selected city's name
    this.input.value = city.name;
    this.query = city.name;
    this.value = city.name;
    this.activeIndex = -1;

    // Hide dropdown
    this._hideDropdown();

    // Call the onChange callback with the full city object
    this.onChange(city);
  }

  _hideDropdown() {
    this.dropdownVisible = false;
    this._removeDropdown();
    this._updateARIAExpanded(false);
  }

  /* ================================== Public Methods ================================== */

  /** Update the options (e.g., if defaultCountry changes) */
  setOptions(options) {
    if (options.defaultCountry !== undefined) {
      this.defaultCountry = options.defaultCountry;
    }
    if (options.placeholder !== undefined) {
      this.placeholder = options.placeholder;
      this.input.placeholder = this.placeholder;
    }
    // Other options like minChars, debounceMs could be updated if needed
  }

  /** Force a re-render of the dropdown (useful if suggestions changed externally) */
  refresh() {
    this._updateDropdown();
  }
}

/* ================================== Default Export ================================== */
// We export the class; there is no default export per se, but we can also export a factory function if desired.
export default CityAutocomplete;
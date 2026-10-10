# CityAutocomplete Component

A reusable autocomplete component for selecting a city/location with fuzzy search, transliteration support, and synchronization via shared state.

## Features

- Fuzzy search (Levenshtein distance ≤ 2)
- Case-insensitive matching
- Transliteration support (Cyrillic ↔ Latin)
- Priority: start-of-word match > contains word > fuzzy
- Debounced input (default 250ms)
- Keyboard navigation (↑/↓/Enter/Esc)
- ARIA attributes for accessibility (role="combobox", etc.)
- Shows top-50 cities of user's country when input is empty and focused
- Skeleton loader while loading dataset
- "Ничего не найдено" state when no matches
- Returns selected city as object: `{id, name, region, country, lat, lon, timezone}`
- Synchronizes with shared state (`state.location` for API, `state.selectedCity` for rich data)

## Usage

### Installation

The component is implemented in vanilla JavaScript and requires no external libraries (though it uses ES modules). Ensure your project supports ES module imports.

### Example

```javascript
import { CityAutocomplete } from './CityAutocomplete.js';
import { useUserCountry } from './hooks/useUserCountry.js';

// Assuming you have an input element in the DOM
const input = document.getElementById('city-input');

const autocomplete = new CityAutocomplete({
  input: input,
  value: state.location, // current value (string)
  onChange: (city) => {
    // Update state when city is selected
    state.location = city.name; // string for API
    state.selectedCity = city;  // object for rich data
    // Trigger re-render if needed
    render();
  },
  defaultCountry: useUserCountry(), // optional: ISO country code for default list
  placeholder: "Например, Москва"   // optional
});

// To destroy the component (e.g., when removing the input from DOM)
// autocomplete.destroy();
```

### Options

| Option | Type | Description |
|--------|------|-------------|
| `input` | `HTMLInputElement` | The input element to enhance. |
| `value` | `string` | Current value of the input (city name). |
| `onChange` | `function(city: Object): void` | Callback when a city is selected. Receives the full city object. |
| `defaultCountry` | `string` | ISO 2-letter country code (e.g., "RU") for showing default list when input is empty and focused. If not provided, attempts to detect user's country. |
| `placeholder` | `string` | Placeholder text for the input. |
| `minChars` | `number` | Minimum characters to trigger search (default: 1). |
| `debounceMs` | `number` | Debounce time for search in milliseconds (default: 250). |

### Data Source

The component expects a local JSON dataset of cities at `../data/cities.json` (relative to the component). Each city object must have the following fields:

- `id` (string): Unique identifier
- `name` (string): City name
- `region` (string): Region/state/province
- `country` (string): ISO 2-letter country code
- `lat` (number): Latitude
- `lon` (number): Longitude
- `timezone` (string): IANA timezone name

The dataset should contain approximately 50–200 KB of data (top cities by population). You can generate or obtain a dataset from sources like [SimpleMaps worldcities](https://simplemaps.com/data/world-cities) or [GeoNames](http://www.geonames.org/export/).

### Integration with State

This component is designed to work with the existing global `state` object in the Clima project. It updates two properties:

- `state.location`: A string representing the city name (used for API requests).
- `state.selectedCity`: An object with full city details (used elsewhere in the app).

When the user selects a city, both properties are updated, and the app is re-rendered to reflect the change in all places that depend on the location (e.g., the plan tab and settings tab).

### Accessibility

The component follows the WAI-ARIA autoruggest pattern:

- The input has `role="combobox"`, `aria-autocomplete="list"`, `aria-expanded`, and `aria-activedescendant`.
- The suggestion list has `role="listbox"` and each suggestion has `role="option"`.
- Keyboard navigation is supported: Arrow Up/Down to move highlight, Enter to select, Escape to close.
- Screen readers will announce the number of results and the selected suggestion (e.g., "Москва, Россия, 3 из 12").

### Customization

You can adjust the appearance by modifying the CSS in `CityAutocomplete.css` or by overriding the styles in your own stylesheet.

### Testing

Unit tests should cover:

- The city search service (transliteration, fuzzy matching, sorting).
- The CityAutocomplete class (opening/closing dropdown, keyboard navigation, selection).
- The useUserCountry hook (detection logic).

An end-to-end test scenario:

1. User focuses on the city input in the settings page → sees top-50 cities of their country.
2. User types "мос" → suggestions include Moscow with correct region/country.
3. User selects Moscow via mouse or keyboard → input shows "Москва".
4. User navigates to the plan tab → city input already shows "Москва".
5. User submits the plan form → the API receives the string "Москва".

## Notes

- The dataset is loaded once via ES module import (`import citiesData from '../data/cities.json' with {type: 'json'};`). If the dataset is large, consider loading it in a web worker to avoid blocking the main thread (not implemented in this version for simplicity).
- The debounce delay helps reduce the frequency of searches while typing.
- The component does not make any external API requests for city search; all search is performed locally on the dataset.
- If the user's country cannot be detected, it defaults to "RU" (Russia). You can override this by passing a `defaultCountry` option.

## Dependencies

No external dependencies. All utilities (transliteration, Levenshtein distance) are implemented locally.

## License

MIT
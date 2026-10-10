// Transliteration map for Cyrillic to Latin and vice versa
// Based on GOST 7.79 RUS-2000 (ISO 9) with some common variations
const cyrillicToLatin = {
  'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'YO',
  'Ж': 'ZH', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
  'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
  'Ф': 'F', 'Х': 'KH', 'Ц': 'TS', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SHCH',
  'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'YU', 'Я': 'YA',
  'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
  'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
  'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
  'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
  'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
};

const latinToCyrillic = {
  'A': 'А', 'B': 'Б', 'V': 'В', 'G': 'Г', 'D': 'Д', 'E': 'Е', 'YO': 'Ё',
  'ZH': 'Ж', 'Z': 'З', 'I': 'И', 'Y': 'Й', 'K': 'К', 'L': 'Л', 'M': 'М',
  'N': 'Н', 'O': 'О', 'P': 'П', 'R': 'Р', 'S': 'С', 'T': 'Т', 'U': 'У',
  'F': 'Ф', 'KH': 'Х', 'TS': 'Ц', 'CH': 'Ч', 'SH': 'Ш', 'SHCH': 'Щ',
  '': 'Ъ', 'Y': 'Ы', "'": 'Ь', 'E': 'Э', 'YU': 'Ю', 'YA': 'Я',
  'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е', 'yo': 'ё',
  'zh': 'ж', 'z': 'з', 'i': 'и', 'y': 'й', 'k': 'к', 'l': 'л', 'm': 'м',
  'n': 'н', 'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
  'f': 'ф', 'kh': 'х', 'ts': 'ц', 'ch': 'ч', 'sh': 'ш', 'shch': 'щ',
  '': 'ъ', 'y': 'ы', "'": 'ь', 'e': 'э', 'yu': 'ю', 'ya': 'я'
};

// Note: The above maps are simplified. For production, consider using a library like translitera.

export function toLatin(str) {
  if (!str) return '';
  // Replace known digraphs first to avoid misinterpretation
  // We'll do a simple character-by-character mapping, but note that some latin letters map to multiple cyrillic and vice versa.
  // For simplicity, we assume input is either purely cyrillic or purely latin with digraphs as defined.
  // We'll handle by trying to match the longest possible latin digraphs first.
  const latinDigraphs = ['zh', 'kh', 'ts', 'ch', 'sh', 'shch', 'yo', 'yu', 'ya'];
  let result = '';
  let i = 0;
  while (i < str.length) {
    let found = false;
    // Check for digraphs
    for (const digraph of latinDigraphs) {
      if (str.substr(i, digraph.length).toLowerCase() === digraph) {
        // Need to match case: if first letter is uppercase, we want uppercase cyrillic?
        // We'll preserve the case of the first letter.
        const ch = str[i];
        const isUpper = ch === ch.toUpperCase() && ch !== ch.toLowerCase();
        const cyr = latinToCyrillic[digraph.toUpperCase()] || latinToCyrillic[digraph];
        result += isUpper ? cyr.toUpperCase() : cyr;
        i += digraph.length;
        found = true;
        break;
      }
    }
    if (found) continue;
    // Single character
    const ch = str[i];
    const latin = cyrillicToLatin[ch] || ch; // fallback to same char if not found
    result += latin;
    i++;
  }
  return result;
}

export function toCyrillic(str) {
  if (!str) return '';
  // We'll do the reverse: try to match longest possible latin digraphs (from our map) but note that latinToCyrillic keys are uppercase.
  // We'll convert the string to uppercase for matching, but preserve case.
  const upper = str.toUpperCase();
  let result = '';
  let i = 0;
  while (i < upper.length) {
    let found = false;
    // Check for digraphs in our latinToCyrillic map (keys are uppercase)
    // We'll check for lengths 4,3,2 (since longest is 'SHCH' = 4)
    for (let len = 4; len >= 2; len--) {
      if (i + len > upper.length) continue;
      const substr = upper.substr(i, len);
      if (latinToCyrillic[substr]) {
        const ch = str[i];
        const isUpper = ch === ch.toUpperCase() && ch !== ch.toLowerCase();
        const cyr = latinToCyrillic[substr];
        result += isUpper ? cyr : cyr.toLowerCase();
        i += len;
        found = true;
        break;
      }
    }
    if (found) continue;
    // Single character
    const ch = str[i];
    const cyr = latinToCyrillic[ch.toUpperCase()] || ch;
    result += (ch === ch.toUpperCase() && ch !== ch.toLowerCase()) ? cyr : cyr.toLowerCase();
    i++;
  }
  return result;
}
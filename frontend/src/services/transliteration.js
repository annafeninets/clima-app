// Транслитерация и «фонетический ключ» для поиска городов независимо от алфавита.
//
// Локальный датасет GeoNames хранит названия латиницей («Moscow»), а пользователь
// вводит «Москва». Оба написания приводятся к одному ключу («moskov» ≈ «moskva»),
// после чего работают обычные prefix/fuzzy-сравнения.

const CYRILLIC = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "yo", ж: "zh", з: "z", и: "i",
  й: "y", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t",
  у: "u", ф: "f", х: "kh", ц: "ts", ч: "ch", ш: "sh", щ: "shch", ъ: "", ы: "y", ь: "",
  э: "e", ю: "yu", я: "ya",
  // украинский, белорусский, сербский, казахский — частые источники названий в GeoNames
  і: "i", ї: "yi", є: "ye", ґ: "g", ў: "u", ј: "j", љ: "lj", њ: "nj", ћ: "c", ђ: "dj",
  џ: "dz", ә: "a", ғ: "g", қ: "k", ң: "n", ө: "o", ұ: "u", ү: "u", һ: "h",
};

const EXTRA_LATIN = { ß: "ss", ø: "o", æ: "ae", œ: "oe", ł: "l", đ: "d", ð: "d", þ: "th", ı: "i" };

/** Кириллица → латиница (ГОСТ-подобная), остальные символы без изменений. */
export function toLatin(text) {
  let out = "";
  for (const char of String(text || "")) {
    const lower = char.toLowerCase();
    if (Object.hasOwn(CYRILLIC, lower)) {
      const latin = CYRILLIC[lower];
      out += char !== lower && latin ? latin[0].toUpperCase() + latin.slice(1) : latin;
    } else {
      out += char;
    }
  }
  return out;
}

function stripDiacritics(text) {
  let out = "";
  for (const char of text.normalize("NFD")) {
    if (/\p{M}/u.test(char)) continue;
    out += EXTRA_LATIN[char] ?? char;
  }
  return out;
}

/**
 * Фонетический ключ: «Москва», «Moscow», «Moskva» → префикс «mosk…».
 * Ключ сохраняет пробелы и дефисы как границы слов.
 */
export function phoneticKey(text) {
  let key = stripDiacritics(toLatin(String(text || "")).toLowerCase());
  key = key.replace(/['’`ʼ.]/g, "");
  key = key.replace(/[^a-z0-9]+/g, " ").trim();
  key = key
    .replace(/shch|sch|sh/g, "s")
    .replace(/zh/g, "z")
    .replace(/kh/g, "h")
    .replace(/ts|tz|tch|ch/g, "C")
    .replace(/x/g, "ks")
    .replace(/q/g, "k")
    .replace(/w/g, "v")
    .replace(/y(?=[aeiou])/g, "")
    .replace(/[yj]/g, "i")
    .replace(/c(?=[eiy])/g, "s")
    .replace(/c/g, "k")
    .replace(/C/g, "c")
    .replace(/(.)\1+/g, "$1");
  return key;
}

export function keyWords(key) {
  return key ? key.split(" ").filter(Boolean) : [];
}

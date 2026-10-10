// Расстояние Левенштейна (вставки, удаления, замены) за O(min(m, n)) памяти.
export function levenshtein(a, b) {
  if (a === b) return 0;
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  if (a.length > b.length) [a, b] = [b, a];

  const row = new Array(a.length + 1);
  for (let i = 0; i <= a.length; i++) row[i] = i;

  for (let j = 1; j <= b.length; j++) {
    let prev = row[0];
    row[0] = j;
    for (let i = 1; i <= a.length; i++) {
      const saved = row[i];
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      row[i] = Math.min(row[i] + 1, row[i - 1] + 1, prev + cost);
      prev = saved;
    }
  }
  return row[a.length];
}

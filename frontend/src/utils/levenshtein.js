// Compute the Levenshtein distance between two strings
// Returns the number of single-character edits (insertions, deletions, substitutions) required to change one string into the other.
// Optimized for short strings (city names) using O(min(m,n)) space.
export function levenshtein(a, b) {
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;

  // Ensure we use the shorter string for the row to minimize memory
  if (a.length > b.length) {
    const temp = a;
    a = b;
    b = temp;
  }

  const row = new Array(a.length + 1);
  for (let i = 0; i <= a.length; i++) {
    row[i] = i;
  }

  for (let j = 1; j <= b.length; j++) {
    let prev = row[0];
    row[0] = j;
    for (let i = 1; i <= a.length; i++) {
      const temp = row[i];
      const cost = (a[i - 1] === b[j - 1]) ? 0 : 1;
      row[i] = Math.min(
        row[i] + 1,          // deletion
        row[i - 1] + 1,      // insertion
        prev + cost          // substitution
      );
      prev = temp;
    }
  }

  return row[a.length];
}
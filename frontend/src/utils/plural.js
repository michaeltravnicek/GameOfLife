/**
 * Czech count agreement: 1 → `one`, 2–4 → `few`, 0 and 5+ → `many`.
 *
 *   plural(n, 'odznak', 'odznaky', 'odznaků')
 */
export function plural(n, one, few, many) {
  if (n === 1) return one;
  if (n >= 2 && n <= 4) return few;
  return many;
}

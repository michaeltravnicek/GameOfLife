/**
 * Up-to-two-letter initials from a name, upper-cased. Falls back to `fallback`
 * when the name is empty/blank.
 *
 *   initials('Jan Novák')      -> 'JN'
 *   initials('madonna')        -> 'M'
 *   initials('', 'GO')         -> 'GO'
 */
export function initials(name, fallback = '?') {
  return String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase() || fallback;
}

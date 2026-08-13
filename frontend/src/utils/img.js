// Helpers for serving the right static WebP variant produced by
// scripts/optimize-images.js (output lives in /img/<name>{,-mobile,-desktop}.webp).

const MOBILE_Q = '(max-width: 768px)';

/** True on phone-width viewports. Safe during SSR (returns false). */
export function isMobileViewport() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_Q).matches;
}

/**
 * Pick the mobile or desktop variant for a static gallery image.
 * `name` is the bare base name without extension, e.g. 'gal0'.
 * Evaluated once at call time — fine for first-paint fallbacks.
 */
export function galVariant(name) {
  return `/img/${name}${isMobileViewport() ? '-mobile' : '-desktop'}.webp`;
}

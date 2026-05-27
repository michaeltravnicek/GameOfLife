/**
 * Single source of truth for tunable client constants.
 *
 * Anywhere you'd be tempted to write a magic number for a page size, debounce
 * delay, cache lifetime, or animation interval — put it here and import it.
 * Saves grep hunts when something feels wrong in prod.
 */

// ── Pagination ────────────────────────────────────────────────────────
export const PAGE_SIZE_EVENTS = 30;
export const PAGE_SIZE_GALLERY = 60;

// ── Interaction timing ────────────────────────────────────────────────
export const SEARCH_DEBOUNCE_MS = 300;
export const HERO_AUTO_CYCLE_MS = 5000;

// How many slides ahead of the cursor we prefetch in the gallery slideshow.
export const GALLERY_PREFETCH_TAIL = 5;

// ── Query cache lifetimes (milliseconds) ──────────────────────────────
//
// "Fresh" = served instantly from cache. After this, we do stale-while-revalidate
// (show old data, refetch in the background). After `MAX_AGE`, we discard
// entirely and the user sees a loading state.
export const CACHE_TTL = {
  DEFAULT:       5 * 60 * 1000,  // 5 min
  HOME:          5 * 60 * 1000,
  EVENTS:        2 * 60 * 1000,  // events list changes more often
  EVENT_DETAIL:      60 * 1000,  // tight because of RSVP / check-in
  GALLERY:       5 * 60 * 1000,
  LEADERBOARD:   5 * 60 * 1000,
  PROFILE:           60 * 1000,
};

export const CACHE_MAX_AGE_MS = 30 * 60 * 1000;  // 30 min — drop entirely

// ── Network resilience ────────────────────────────────────────────────
//
// Transient failures (a dropped connection, a 5xx, or — most often on the
// Render free tier — a slow cold-start that times out) are retried
// automatically before the user ever sees an error. This is the single
// biggest cause of "the page loaded empty / no events showed up".
export const QUERY_MAX_RETRIES = 2;          // extra attempts after the first
export const QUERY_RETRY_BASE_MS = 700;      // backoff grows: 700ms, 1400ms, …

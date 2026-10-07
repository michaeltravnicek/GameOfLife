import { invalidateQuery } from './queryCache';

/**
 * Every client cache key, and the groups of them a write makes stale.
 *
 * A prefetch in routePreload only helps when it writes the exact key the page
 * reads, and an invalidation only works when its prefix matches — so both
 * sides build their keys here instead of spelling the strings out.
 */
export const queryKeys = {
  hero: 'hero',
  checkinEvents: 'checkin-events',
  seasons: 'seasons',
  likedPhotos: 'photos:liked',
  galleryMonths: 'gallery:months',
  galleryUploadEvents: 'gallery-upload-past-events',
  adminFeedbacks: 'admin:feedbacks',
  homeUpcoming: 'events:upcoming|Vše|',
  homeLeaderboard: 'leaderboard:home',
  event: (slug) => `event:${slug}`,
  // The events page: one key per filter combination.
  events: (city, season, q) => `events:${city}|${season}|${q}`,
  leaderboard: (seasonId) => `leaderboard:${seasonId}`,
  // One gallery month's first page; `month` is 'YYYY-MM' or 'unknown'.
  galleryMonth: (month) => `gallery:month:${month}`,
  profile: (username, seasonKey) => (
    seasonKey ? `profile:${username}:season:${seasonKey}` : `profile:${username}`
  ),
  player: (userId, seasonKey) => (
    seasonKey ? `player:${userId}:season:${seasonKey}` : `player:${userId}`
  ),
};

const EVENT_LIST_KEYS = new Set([queryKeys.hero, queryKeys.checkinEvents]);

/** An event was created, edited or RSVP'd: every list and carousel showing it. */
export function invalidateEventLists(slug) {
  invalidateQuery((k) => k.startsWith('events:') || EVENT_LIST_KEYS.has(k)
    || (slug !== undefined && k === queryKeys.event(slug)));
}

/** Points, attendance or a player's name changed: boards, profiles, players. */
export function invalidateScores() {
  invalidateQuery((k) => k.startsWith('leaderboard:') || k.startsWith('profile:')
    || k.startsWith('player:'));
}

/** An event is gone, and with it its photos. */
export function invalidateGallery() {
  invalidateQuery((k) => k.startsWith('gallery'));
}

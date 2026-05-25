/**
 * Route chunk + data preloader.
 *
 * Wired to <Link onMouseEnter> and <Link onFocus> so by the time the user
 * actually clicks, both the JS chunk and the initial API payload are usually
 * already in memory. Result: navigation feels instant on warm links.
 *
 * `import()` is module-cached by Vite, so calling the same importer here and
 * inside `lazy()` in App.jsx shares one chunk download.
 */

import { prefetchQuery } from './queryCache';
import { CACHE_TTL, PAGE_SIZE_EVENTS, PAGE_SIZE_GALLERY } from '../constants/config';
import {
  fetchEvents,
  fetchGallery,
  fetchLeaderboard,
  fetchHero,
  fetchStats,
  fetchEventDetail,
  fetchProfile,
} from './api';

// Static paths only — dynamic params like `/akce/:slug` are preloaded ad-hoc
// at the call site if we want them (e.g. on EventCard hover).
const importers = {
  '/': () => import('../pages/Home/HomePage'),
  '/akce': () => import('../pages/Events/EventsPage'),
  '/galerie': () => import('../pages/Gallery/GalleryPage'),
  '/leaderboard': () => import('../pages/Leaderboard/LeaderboardPage'),
  '/profil': () => import('../pages/Profile/ProfilePage'),
  '/o-bodech': () => import('../pages/OBodech/OBodechPage'),
  '/historie': () => import('../pages/Historie/HistoriePage'),
  '/prihlasit': () => import('../pages/Login/LoginPage'),
  '/registrace': () => import('../pages/Register/RegisterPage'),
};

// The home page is composed from several endpoints now (the old /home/ is gone),
// so warming it means warming each piece the page reads on mount.
const warmHome = () => {
  prefetchQuery('hero', fetchHero);
  prefetchQuery('stats', fetchStats);
  prefetchQuery(
    'events:upcoming|Vše|',
    () => fetchEvents({ limit: PAGE_SIZE_EVENTS, offset: 0, period: 'upcoming' }),
  );
  prefetchQuery('leaderboard:home', () => fetchLeaderboard('active', { limit: 10 }));
};

const dataWarmers = {
  '/': warmHome,
  '/akce': () => prefetchQuery(
    'events:upcoming|Vše|',
    () => fetchEvents({ limit: PAGE_SIZE_EVENTS, offset: 0, period: 'upcoming' }),
  ),
  '/galerie': () => prefetchQuery(
    'gallery:first',
    () => fetchGallery({ limit: PAGE_SIZE_GALLERY, offset: 0 }),
  ),
  '/leaderboard': () => prefetchQuery(
    'leaderboard:active',
    () => fetchLeaderboard('active'),
  ),
};

const preloadedChunks = new Set();
const preloadedData = new Set();

// Dynamic-segment chunks — loaded once, then reused across slugs/usernames.
const importEventDetail = () => import('../pages/EventDetail/EventDetailPage');
const importProfile = () => import('../pages/Profile/ProfilePage');

let eventDetailChunkPromise = null;
let profileChunkPromise = null;

/**
 * Preload the EventDetail chunk + this specific event's data.
 * Call on hover/focus of an event card.
 */
export function preloadEventDetail(slug) {
  if (!eventDetailChunkPromise) {
    eventDetailChunkPromise = importEventDetail().catch(() => {
      eventDetailChunkPromise = null;
    });
  }
  if (slug) {
    prefetchQuery(`event:${slug}`, () => fetchEventDetail(slug), { ttl: 60 * 1000 });
  }
}

/**
 * Preload the Profile chunk + a specific user's profile data.
 */
export function preloadProfile(username) {
  if (!profileChunkPromise) {
    profileChunkPromise = importProfile().catch(() => {
      profileChunkPromise = null;
    });
  }
  if (username) {
    prefetchQuery(`profile:${username}`, () => fetchProfile(username), { ttl: 60 * 1000 });
  }
}

/**
 * Preload both the JS chunk and the initial data for a known path.
 * Safe to call repeatedly — each path runs at most once per session.
 */
export function preloadRoute(path) {
  // Strip query/hash for the lookup.
  const clean = path.split(/[?#]/)[0];

  if (!preloadedChunks.has(clean) && importers[clean]) {
    preloadedChunks.add(clean);
    importers[clean]().catch(() => {
      // Don't block UX on a failed preload — the user click will retry.
      preloadedChunks.delete(clean);
    });
  }
  if (!preloadedData.has(clean) && dataWarmers[clean]) {
    preloadedData.add(clean);
    dataWarmers[clean]();
  }
}

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearCache, prefetchQuery } from './queryCache';
import {
  invalidateEventLists, invalidateGallery, invalidateScores, queryKeys,
} from './queryKeys';

const ALL = [
  queryKeys.hero, queryKeys.checkinEvents, queryKeys.homeUpcoming,
  queryKeys.events('Vše', 'all', ''), queryKeys.event('a'), queryKeys.event('b'),
  queryKeys.homeLeaderboard, queryKeys.leaderboard('active'),
  queryKeys.profile('jan'), queryKeys.profile('jan', 3), queryKeys.player(7),
  queryKeys.galleryFirst, queryKeys.seasons,
];

// A key is still cached when prefetching it again does not call the fetcher.
async function dropped() {
  const gone = [];
  for (const key of ALL) {
    const fetcher = vi.fn().mockResolvedValue(null);
    await prefetchQuery(key, fetcher);
    if (fetcher.mock.calls.length) gone.push(key);
  }
  return gone;
}

describe('queryKeys invalidation groups', () => {
  beforeEach(async () => {
    clearCache();
    await Promise.all(ALL.map((key) => prefetchQuery(key, () => Promise.resolve(key))));
  });

  it('event lists: every events page, the carousels and the one edited event', async () => {
    invalidateEventLists('a');
    expect(await dropped()).toEqual([
      'hero', 'checkin-events', 'events:upcoming|Vše|', 'events:Vše|all|', 'event:a',
    ]);
  });

  it('scores: boards, profiles and players, nothing else', async () => {
    invalidateScores();
    expect(await dropped()).toEqual([
      'leaderboard:home', 'leaderboard:active',
      'profile:jan', 'profile:jan:season:3', 'player:7',
    ]);
  });

  it('gallery', async () => {
    invalidateGallery();
    expect(await dropped()).toEqual(['gallery:first']);
  });
});

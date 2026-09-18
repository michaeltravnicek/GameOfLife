import { describe, expect, it, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import {
  useCachedQuery,
  prefetchQuery,
  invalidateQuery,
  refetchQuery,
  clearCache,
} from './queryCache';
import { CACHE_MAX_ENTRIES } from '../constants/config';

describe('queryCache', () => {
  beforeEach(() => {
    clearCache();
  });

  it('caches a fresh result so a second consumer skips the fetcher', async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 'one' });

    const { result, unmount } = renderHook(() =>
      useCachedQuery('test-key', fetcher, { ttl: 60_000 })
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ value: 'one' });
    expect(fetcher).toHaveBeenCalledTimes(1);
    unmount();

    // Second mount must read from cache, no extra fetch.
    const second = renderHook(() =>
      useCachedQuery('test-key', fetcher, { ttl: 60_000 })
    );
    expect(second.result.current.data).toEqual({ value: 'one' });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('dedupes concurrent fetches for the same key', async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 'shared' });

    const a = prefetchQuery('dedup-key', fetcher);
    const b = prefetchQuery('dedup-key', fetcher);

    const [aVal, bVal] = await Promise.all([a, b]);
    expect(aVal).toEqual({ value: 'shared' });
    expect(bVal).toEqual({ value: 'shared' });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('invalidateQuery with a string drops the matching entry', async () => {
    const fetcher = vi.fn().mockResolvedValue({ n: 1 });
    await prefetchQuery('drop-me', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);

    invalidateQuery('drop-me');
    // After invalidation, prefetch should re-fetch.
    await prefetchQuery('drop-me', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('invalidateQuery with a predicate drops every matching key', async () => {
    const fetcher = vi.fn().mockResolvedValue({});
    await prefetchQuery('events:upcoming', fetcher);
    await prefetchQuery('events:past', fetcher);
    await prefetchQuery('home', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(3);

    invalidateQuery((k) => k.startsWith('events:'));
    await prefetchQuery('events:upcoming', fetcher);
    await prefetchQuery('events:past', fetcher);
    await prefetchQuery('home', fetcher);  // home is still cached
    expect(fetcher).toHaveBeenCalledTimes(5);  // +2 events, home was cached
  });

  it('clearCache empties everything', async () => {
    const fetcher = vi.fn().mockResolvedValue({});
    await prefetchQuery('k1', fetcher);
    await prefetchQuery('k2', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(2);

    clearCache();
    await prefetchQuery('k1', fetcher);
    await prefetchQuery('k2', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(4);
  });

  it('stale-while-revalidate: returns cached value immediately and refetches', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ tag: 'old' })
      .mockResolvedValueOnce({ tag: 'fresh' });

    // First call seeds the cache.
    await prefetchQuery('swr-key', fetcher);

    // Mount with ttl=0 so the entry is immediately stale → expect old data
    // returned at once, plus a background refetch.
    const { result } = renderHook(() =>
      useCachedQuery('swr-key', fetcher, { ttl: 0, maxAge: 60_000 })
    );
    expect(result.current.data).toEqual({ tag: 'old' });  // immediate
    await waitFor(() => expect(result.current.data).toEqual({ tag: 'fresh' }));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('surfaces a non-retryable (4xx) error via the hook', async () => {
    // A 4xx is deterministic, so it's surfaced immediately without any retry —
    // which also keeps this test fast (no backoff wait).
    const err = Object.assign(new Error('boom'), { response: { status: 404 } });
    const fetcher = vi.fn().mockRejectedValue(err);
    const { result } = renderHook(() =>
      useCachedQuery('err-key', fetcher, { ttl: 60_000 })
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('retries a transient failure, then surfaces the eventual success', async () => {
    // No `response` ⇒ looks like a network/timeout error ⇒ retryable. The fix
    // for "the page sometimes loads empty": one blip no longer surfaces.
    const fetcher = vi.fn()
      .mockRejectedValueOnce(new Error('network blip'))
      .mockResolvedValueOnce({ ok: true });
    const { result } = renderHook(() =>
      useCachedQuery('retry-key', fetcher, { ttl: 60_000 })
    );
    await waitFor(
      () => expect(result.current.data).toEqual({ ok: true }),
      { timeout: 3000 },
    );
    expect(result.current.error).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  // Regressions from the September review — see the plan's frontend section.

  it('a key change clears the previous key\'s data while the new one loads', async () => {
    const fetcher = vi.fn((key) => Promise.resolve({ key }));
    let resolveB;
    const fetchFor = (key) => (key === 'b'
      ? new Promise((r) => { resolveB = r; })
      : fetcher(key));
    const { result, rerender } = renderHook(
      ({ key }) => useCachedQuery(key, () => fetchFor(key), { ttl: 60_000 }),
      { initialProps: { key: 'a' } },
    );
    await waitFor(() => expect(result.current.data).toEqual({ key: 'a' }));

    rerender({ key: 'b' });
    // Event A must not be rendered (or acted on) as if it were event B.
    await waitFor(() => expect(result.current.loading).toBe(true));
    expect(result.current.data).toBeUndefined();

    resolveB({ key: 'b' });
    await waitFor(() => expect(result.current.data).toEqual({ key: 'b' }));
  });

  it('a key change clears the previous key\'s error', async () => {
    const err = Object.assign(new Error('nope'), { response: { status: 404 } });
    const fetchFor = (key) => (key === 'missing'
      ? Promise.reject(err)
      : Promise.resolve({ key }));
    const { result, rerender } = renderHook(
      ({ key }) => useCachedQuery(key, () => fetchFor(key), { ttl: 60_000 }),
      { initialProps: { key: 'missing' } },
    );
    await waitFor(() => expect(result.current.error).toBe(err));

    rerender({ key: 'present' });
    await waitFor(() => expect(result.current.data).toEqual({ key: 'present' }));
    expect(result.current.error).toBeNull();
  });

  it('an eviction does not refetch a query that has since been disabled', async () => {
    // Logout: the user is cleared first, then the cache. The signed-in-only
    // query must not fire one last time as the anonymous user.
    const fetcher = vi.fn().mockResolvedValue({ liked: [1] });
    const { result, rerender } = renderHook(
      ({ enabled }) => useCachedQuery('liked', fetcher, { ttl: 60_000, enabled }),
      { initialProps: { enabled: true } },
    );
    await waitFor(() => expect(result.current.data).toEqual({ liked: [1] }));
    expect(fetcher).toHaveBeenCalledTimes(1);

    rerender({ enabled: false });
    clearCache();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('refetchQuery keeps subscribers on their current value until the new one lands', async () => {
    let resolveNext;
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ n: 1 })
      .mockImplementationOnce(() => new Promise((r) => { resolveNext = r; }));
    const { result } = renderHook(() => useCachedQuery('k', fetcher, { ttl: 60_000 }));
    await waitFor(() => expect(result.current.data).toEqual({ n: 1 }));

    const pending = refetchQuery('k', fetcher);
    await waitFor(() => expect(resolveNext).toBeTypeOf('function'));
    expect(result.current.data).toEqual({ n: 1 });  // no blank frame
    resolveNext({ n: 2 });
    await pending;
    await waitFor(() => expect(result.current.data).toEqual({ n: 2 }));
  });

  it('evicts the oldest entries once the cache is full', async () => {
    const fetcher = vi.fn().mockResolvedValue({});
    for (let i = 0; i < CACHE_MAX_ENTRIES + 5; i += 1) {
      await prefetchQuery(`fill:${i}`, fetcher);
    }
    expect(fetcher).toHaveBeenCalledTimes(CACHE_MAX_ENTRIES + 5);
    await prefetchQuery('fill:0', fetcher);  // the first one is gone
    expect(fetcher).toHaveBeenCalledTimes(CACHE_MAX_ENTRIES + 6);
    await prefetchQuery(`fill:${CACHE_MAX_ENTRIES + 4}`, fetcher);  // the last is still there
    expect(fetcher).toHaveBeenCalledTimes(CACHE_MAX_ENTRIES + 6);
  });
});

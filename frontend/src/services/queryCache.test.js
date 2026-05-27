import { describe, expect, it, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import {
  useCachedQuery,
  prefetchQuery,
  invalidateQuery,
  clearCache,
} from './queryCache';

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
});

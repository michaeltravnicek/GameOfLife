import { useEffect, useRef, useState } from 'react';
import {
  CACHE_MAX_AGE_MS, CACHE_TTL, QUERY_MAX_RETRIES, QUERY_RETRY_BASE_MS,
} from '../constants/config';

/**
 * Tiny in-memory query cache with TTL, in-flight deduplication, and
 * stale-while-revalidate semantics.
 *
 * Why: every page navigation re-mounts and re-fetches the same API endpoints.
 * For users clicking around (Home -> Events -> Home -> Profile -> Home) that's
 * the same response downloaded 3x. With this cache, the second visit reads
 * from memory instantly and (if stale) refreshes in the background.
 *
 * Why server cares: fewer concurrent requests during normal navigation ->
 * fewer Gunicorn workers needed at peak -> lower RAM ceiling.
 *
 * Public API:
 *   useCachedQuery(key, fetcher, options)  -> { data, error, loading, refetch }
 *   prefetchQuery(key, fetcher, options)    -> Promise<value>  (fire and forget)
 *   invalidateQuery(key | predicate)        -> void
 *   clearCache()                            -> void  (e.g. on logout)
 */

const DEFAULT_TTL_MS = CACHE_TTL.DEFAULT;
const DEFAULT_MAX_AGE_MS = CACHE_MAX_AGE_MS;

const cache = new Map();        // key -> { value, fetchedAt }
const inflight = new Map();      // key -> Promise
const subscribers = new Map();   // key -> Set<callback>

function notify(key) {
  const subs = subscribers.get(key);
  if (!subs) return;
  for (const cb of subs) cb();
}

function subscribe(key, cb) {
  let set = subscribers.get(key);
  if (!set) {
    set = new Set();
    subscribers.set(key, set);
  }
  set.add(cb);
  return () => {
    set.delete(cb);
    if (set.size === 0) subscribers.delete(key);
  };
}

function getEntry(key) {
  return cache.get(key);
}

function setEntry(key, value) {
  cache.set(key, { value, fetchedAt: Date.now() });
  notify(key);
}

/**
 * A failure is worth retrying only if it's transient: a network/timeout error
 * (no HTTP response at all — common on Render cold starts) or a 5xx. A 4xx is
 * deterministic (bad request, 404), so retrying it just delays the error.
 */
function isRetryable(err) {
  const status = err?.response?.status;
  if (status === undefined) return true;   // network error / timeout
  return status >= 500 && status < 600;
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run `fetcher`, retrying transient failures with linear backoff. This is the
 * fix for "sometimes the page loads with no data" — a single dropped/slow
 * request no longer surfaces as an empty page.
 */
function fetchWithRetry(fetcher, attempt = 0) {
  return Promise.resolve()
    .then(fetcher)
    .catch((err) => {
      if (attempt < QUERY_MAX_RETRIES && isRetryable(err)) {
        return delay(QUERY_RETRY_BASE_MS * (attempt + 1))
          .then(() => fetchWithRetry(fetcher, attempt + 1));
      }
      throw err;
    });
}

/**
 * Execute the fetcher with in-flight dedup. If another caller is already
 * fetching this key, both get the same Promise.
 */
function dedupedFetch(key, fetcher) {
  const existing = inflight.get(key);
  if (existing) return existing;
  const promise = fetchWithRetry(fetcher)
    .then((value) => {
      setEntry(key, value);
      return value;
    })
    .finally(() => inflight.delete(key));
  inflight.set(key, promise);
  return promise;
}

/** Fire-and-forget — useful for preloading on Link hover. */
export function prefetchQuery(key, fetcher, { ttl = DEFAULT_TTL_MS } = {}) {
  const entry = getEntry(key);
  if (entry && Date.now() - entry.fetchedAt < ttl) return Promise.resolve(entry.value);
  return dedupedFetch(key, fetcher).catch(() => undefined);
}

/** Drop matching entries; pass a string for exact match or a predicate fn. */
export function invalidateQuery(keyOrPredicate) {
  if (typeof keyOrPredicate === 'function') {
    for (const k of cache.keys()) {
      if (keyOrPredicate(k)) {
        cache.delete(k);
        notify(k);
      }
    }
  } else {
    cache.delete(keyOrPredicate);
    notify(keyOrPredicate);
  }
}

export function clearCache() {
  const keys = Array.from(cache.keys());
  cache.clear();
  for (const k of keys) notify(k);
}

/**
 * React hook. Returns { data, error, loading, refetch }.
 *
 * Behavior:
 *   - If a fresh entry exists (< ttl), use it immediately, no fetch.
 *   - If a stale entry exists (>= ttl but < maxAge), show it while refetching
 *     in the background (stale-while-revalidate).
 *   - If no entry (or entry is past maxAge), fetch and show loading state.
 *   - In-flight requests for the same key are deduplicated.
 *   - Subscribes to cache notifications so sibling consumers stay in sync.
 *
 * Pass `enabled: false` to skip the request (e.g. when a route param is missing).
 */
export function useCachedQuery(key, fetcher, options = {}) {
  const {
    ttl = DEFAULT_TTL_MS,
    maxAge = DEFAULT_MAX_AGE_MS,
    enabled = true,
  } = options;

  // Snapshot current entry up-front so the first render already has data
  // when we navigate back to a cached page.
  const initialEntry = enabled ? getEntry(key) : undefined;
  // Reading the module-level cache (and the clock) during render is the whole
  // point of this hook: a cached page must paint with its data on the first
  // render, not flash empty and fill in from an effect one frame later.
  // eslint-disable-next-line react-hooks/purity
  const initialFresh = !!initialEntry && Date.now() - initialEntry.fetchedAt < ttl;

  const [data, setData] = useState(initialEntry?.value);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(enabled && !initialFresh);

  // Keep the latest fetcher in a ref so changing it doesn't retrigger the effect.
  // Callers pass an inline arrow, so the fetcher is a new function every
  // render. Storing it in a ref is what stops that from re-running the fetch
  // on every render; putting it in the dependency array would be an infinite
  // loop, and the value is only ever read inside the effect.
  const fetcherRef = useRef(fetcher);
  // eslint-disable-next-line react-hooks/refs
  fetcherRef.current = fetcher;

  // This effect *is* the data-fetching state machine — loading/data/error only
  // exist to mirror an async external system into React.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }

    let cancelled = false;

    // Subscribe to broadcast updates from siblings / refetches.
    // When an entry is dropped (clearCache on logout/login, invalidateQuery),
    // we refetch instead of just blanking — otherwise the page sits on empty
    // state until the user navigates away and back.
    const unsubscribe = subscribe(key, () => {
      if (cancelled) return;
      const next = getEntry(key);
      if (next) {
        setData(next.value);
        return;
      }
      setData(undefined);
      setLoading(true);
      dedupedFetch(key, () => fetcherRef.current())
        .then((value) => { if (!cancelled) { setData(value); setError(null); } })
        .catch((e) => { if (!cancelled) setError(e); })
        .finally(() => { if (!cancelled) setLoading(false); });
    });

    const entry = getEntry(key);
    const now = Date.now();

    if (entry) {
      const age = now - entry.fetchedAt;
      setData(entry.value);
      if (age < ttl) {
        // Fresh — done.
        setLoading(false);
        return () => { cancelled = true; unsubscribe(); };
      }
      // Stale but usable: keep showing the old value, refresh in background.
      if (age < maxAge) {
        setLoading(false);
      } else {
        setLoading(true);
      }
    } else {
      setLoading(true);
    }

    dedupedFetch(key, () => fetcherRef.current())
      .then((value) => {
        if (cancelled) return;
        setData(value);
        setError(null);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [key, enabled, ttl, maxAge]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const refetch = () => {
    // Forget cached value so the next consumer fetches fresh.
    cache.delete(key);
    return dedupedFetch(key, () => fetcherRef.current());
  };

  return { data, error, loading, refetch };
}

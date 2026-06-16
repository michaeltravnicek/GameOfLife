import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useCachedQuery } from './queryCache';
import { reportError } from './errors';

/**
 * Cached, paginated data hook.
 *
 * Both `/events` and `/galerie` follow the same shape:
 *   - The FIRST page lives in the shared cache (so navigation back is instant).
 *   - Pages loaded via "Načíst další" are appended locally — they don't get
 *     cached separately, because users rarely revisit the same offset twice.
 *   - Whenever the cache key changes (e.g. user changes a filter), local
 *     pages are dropped.
 *
 * Usage:
 *   const { items, hasMore, totalCount, loading, loadingMore, loadMore } =
 *     usePaginatedQuery({
 *       cacheKey: `events:${tab}|${city}|${q}`,
 *       fetcher: (offset, limit) => fetchEvents({ ...filters, offset, limit }),
 *       pageSize: PAGE_SIZE_EVENTS,
 *       ttl: CACHE_TTL.EVENTS,
 *       errorMessage: 'Nepodařilo se načíst další akce.',
 *       extractItems: (response) => response.events || [],
 *       extractHasMore: (response) => !!response.has_more,
 *       extractCount: (response) => response.count ?? 0,
 *     });
 */
export function usePaginatedQuery({
  cacheKey,
  fetcher,
  pageSize,
  ttl,
  errorMessage = 'Nepodařilo se načíst další stránku.',
  extractItems,
  extractHasMore,
  extractCount,
}) {
  const [extraItems, setExtraItems] = useState([]);
  const [extraHasMore, setExtraHasMore] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);

  // Each filter change increments reqId. In-flight `loadMore` results
  // arriving after a filter change are discarded.
  const reqIdRef = useRef(0);

  // First page is owned by the shared cache.
  const {
    data: firstPage, loading: firstLoading, error: firstError, refetch,
  } = useCachedQuery(
    cacheKey,
    () => fetcher(0, pageSize),
    { ttl },
  );

  // Reset local accumulator whenever the cache key (= filter combo) flips.
  useEffect(() => {
    setExtraItems([]);
    setExtraHasMore(null);
    setLoadingMore(false);
    reqIdRef.current += 1;
  }, [cacheKey]);

  const firstItems = extractItems(firstPage || {});
  const items = useMemo(
    () => (extraItems.length ? [...firstItems, ...extraItems] : firstItems),
    [firstItems, extraItems],
  );
  const totalCount = firstPage ? extractCount(firstPage) : items.length;
  const hasMore = extraHasMore !== null ? extraHasMore : (firstPage ? extractHasMore(firstPage) : false);
  const loading = firstLoading && items.length === 0;
  // Only treat the first page as "failed" when we have nothing to show. A
  // background refresh that fails over already-rendered data isn't an error
  // worth blanking the page for.
  const error = items.length === 0 ? firstError : null;

  const loadMore = useCallback(() => {
    if (loadingMore || !hasMore) return Promise.resolve();
    const myReq = reqIdRef.current;
    setLoadingMore(true);
    return fetcher(items.length, pageSize)
      .then((d) => {
        if (reqIdRef.current !== myReq) return; // filter changed mid-flight
        setExtraItems((prev) => [...prev, ...extractItems(d)]);
        setExtraHasMore(extractHasMore(d));
      })
      .catch(reportError(errorMessage))
      .finally(() => {
        if (reqIdRef.current === myReq) setLoadingMore(false);
      });
  }, [
    fetcher, items.length, pageSize, hasMore, loadingMore,
    errorMessage, extractItems, extractHasMore,
  ]);

  return {
    items, hasMore, totalCount, loading, loadingMore, loadMore, firstPage, error, retry: refetch,
  };
}

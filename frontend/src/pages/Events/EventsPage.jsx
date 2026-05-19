import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchEvents } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import EventCard from '../../components/EventCard/EventCard';
import TabBar from '../../components/TabBar/TabBar';
import SearchInput from '../../components/SearchInput/SearchInput';
import './EventsPage.css';

const PAGE_SIZE = 30;
const SEARCH_DEBOUNCE_MS = 300;

const TABS = [
  { key: 'upcoming', label: 'Nadcházející' },
  { key: 'past', label: 'Proběhlo' },
  { key: 'all', label: 'Vše' },
];

export default function EventsPage() {
  const [tab, setTab] = useState('upcoming');
  const [city, setCity] = useState('Vše');
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Pages appended via "Load more" — kept outside the cache because they're
  // composed on the fly and rarely revisited at the same offset.
  const [extraEvents, setExtraEvents] = useState([]);
  const [extraHasMore, setExtraHasMore] = useState(null); // null = use first-page value
  const [loadingMore, setLoadingMore] = useState(false);
  // Cities are sticky across filter changes — once loaded, keep showing.
  const [cities, setCities] = useState([]);
  const reqIdRef = useRef(0);

  // Debounce the search query (avoids one API call per keystroke).
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);

  const buildParams = useCallback((offset) => {
    const params = { limit: PAGE_SIZE, offset };
    if (tab !== 'all') params.period = tab;
    if (city !== 'Vše') params.city = city;
    if (debouncedQuery.trim()) params.q = debouncedQuery.trim();
    return params;
  }, [tab, city, debouncedQuery]);

  // Per-filter cache key — the same tab/city/query combination hits cache on
  // re-mount without a network round-trip.
  const cacheKey = useMemo(
    () => `events:${tab}|${city}|${debouncedQuery.trim()}`,
    [tab, city, debouncedQuery],
  );

  // First page lives in the shared cache (stale-while-revalidate enabled).
  const firstPageParams = useMemo(() => buildParams(0), [buildParams]);
  const { data: firstPage, loading: firstLoading } = useCachedQuery(
    cacheKey,
    () => fetchEvents(firstPageParams),
    { ttl: 2 * 60 * 1000 }, // 2 min — events list changes occasionally
  );

  // Whenever filter changes, drop locally-accumulated extra pages.
  useEffect(() => {
    setExtraEvents([]);
    setExtraHasMore(null);
    reqIdRef.current += 1;
  }, [cacheKey]);

  const firstEvents = firstPage?.events || [];
  const firstCities = firstPage?.cities || [];
  const totalCount = firstPage?.count ?? firstEvents.length + extraEvents.length;

  const events = useMemo(
    () => (extraEvents.length ? [...firstEvents, ...extraEvents] : firstEvents),
    [firstEvents, extraEvents],
  );
  const hasMore = extraHasMore !== null ? extraHasMore : !!firstPage?.has_more;

  const loadMore = useCallback(() => {
    if (loadingMore || !hasMore) return;
    const myReq = reqIdRef.current; // freeze for this load
    setLoadingMore(true);
    fetchEvents(buildParams(events.length))
      .then((d) => {
        if (reqIdRef.current !== myReq) return; // user changed filters meanwhile
        setExtraEvents((prev) => [...prev, ...(d.events || [])]);
        setExtraHasMore(!!d.has_more);
      })
      .catch(() => {})
      .finally(() => {
        if (reqIdRef.current === myReq) setLoadingMore(false);
      });
  }, [buildParams, events.length, hasMore, loadingMore]);

  // Surface cities from whatever cache entry is currently active.
  useEffect(() => {
    if (firstCities.length) setCities(firstCities);
  }, [firstCities]);

  const loading = firstLoading && events.length === 0;

  const cityChoices = useMemo(
    () => ['Vše', ...cities.map((c) => c.name)],
    [cities],
  );

  // Group already-loaded events into upcoming / past for display.
  const { upcoming, past } = useMemo(() => ({
    upcoming: events
      .filter((ev) => !ev.is_past)
      .sort((a, b) => new Date(a.date) - new Date(b.date)),
    past: events
      .filter((ev) => ev.is_past)
      .sort((a, b) => new Date(b.date) - new Date(a.date)),
  }), [events]);

  const empty = !loading && events.length === 0;

  return (
    <div className="events-page">
      <div className="stage" />
      <div className="grain" />

      <header className="hero">
        <div className="eyebrow">Kalendář · Sezóna 2025/26</div>
        <h1>Events</h1>
        <p className="tagline">Kompletní seznam akcí. Od karaoke přes nahou míli, deskovky až po bruslení. Sbírej body, hraj život.</p>
        <div className="divider" />
      </header>

      <section className="controls">
        <TabBar tabs={TABS} active={tab} onChange={setTab} />
        <SearchInput
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Hledat akci…"
        />
      </section>

      <section className="locations">
        {cityChoices.map((c) => (
          <button key={c} className={`loc${city === c ? ' on' : ''}`} onClick={() => setCity(c)}>
            {c}
          </button>
        ))}
      </section>

      <main className="events-main">
        {loading && <div className="empty">Načítám akce…</div>}
        {empty && <div className="empty">Žádné akce nenalezeny.</div>}

        {upcoming.length > 0 && (
          <>
            <div className="group-label">Nadcházející</div>
            <div className="events-grid">
              {upcoming.map((ev) => <EventCard key={ev.id} event={ev} theme="light" />)}
            </div>
          </>
        )}
        {past.length > 0 && (
          <>
            <div className="group-label past">Proběhlo</div>
            <div className="events-grid">
              {past.map((ev) => <EventCard key={ev.id} event={ev} theme="light" />)}
            </div>
          </>
        )}

        {hasMore && !loading && (
          <div className="load-more-row">
            <button
              type="button"
              className="loc"
              onClick={loadMore}
              disabled={loadingMore}
            >
              {loadingMore ? 'Načítám…' : `Načíst další (${totalCount - events.length})`}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

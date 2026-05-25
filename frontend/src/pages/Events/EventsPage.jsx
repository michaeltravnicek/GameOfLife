import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchEvents, fetchSeasons } from '../../services/api';
import { usePaginatedQuery } from '../../services/usePaginatedQuery';
import { useCachedQuery } from '../../services/queryCache';
import { useAuth } from '../../context/AuthContext';
import { CACHE_TTL, PAGE_SIZE_EVENTS, SEARCH_DEBOUNCE_MS } from '../../constants/config';
import EventCard from '../../components/EventCard/EventCard';
import TabBar from '../../components/TabBar/TabBar';
import SearchInput from '../../components/SearchInput/SearchInput';
import './EventsPage.css';

const TABS = [
  { key: 'upcoming', label: 'Nadcházející' },
  { key: 'past', label: 'Proběhlo' },
  { key: 'all', label: 'Vše' },
];

// Server response → local fields. Used by the pagination hook.
const extractEvents = (r) => r.events || [];
const extractHasMore = (r) => !!r.has_more;
const extractCount = (r) => r.count ?? 0;

export default function EventsPage() {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState('upcoming');
  const [city, setCity] = useState('Vše');
  const [season, setSeason] = useState('all'); // 'all' or a season id
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  // Cities are returned only on the first page; we keep them locally so
  // they survive filter changes.
  const [cities, setCities] = useState([]);

  // Season selector options (All-time + each season).
  const { data: seasonsData } = useCachedQuery('seasons', fetchSeasons, { ttl: CACHE_TTL.LEADERBOARD });
  const seasonChoices = useMemo(
    () => [{ id: 'all', name: 'Vše' }, ...(seasonsData?.seasons || []).map((s) => ({ id: s.id, name: s.name }))],
    [seasonsData],
  );

  // Debounce search input so we don't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);

  // Build the per-request params from current filters.
  const buildParams = useCallback((offset, limit) => {
    const params = { limit, offset };
    if (tab !== 'all') params.period = tab;
    if (city !== 'Vše') params.city = city;
    if (season !== 'all') params.season_id = season;
    if (debouncedQuery.trim()) params.q = debouncedQuery.trim();
    return params;
  }, [tab, city, season, debouncedQuery]);

  // Cache key encodes the filter combo so going back to the same filters
  // hits cache instantly.
  const cacheKey = useMemo(
    () => `events:${tab}|${city}|${season}|${debouncedQuery.trim()}`,
    [tab, city, season, debouncedQuery],
  );

  const {
    items: events, hasMore, totalCount, loading, loadingMore, loadMore, firstPage,
  } = usePaginatedQuery({
    cacheKey,
    fetcher: (offset, limit) => fetchEvents(buildParams(offset, limit)),
    pageSize: PAGE_SIZE_EVENTS,
    ttl: CACHE_TTL.EVENTS,
    errorMessage: 'Nepodařilo se načíst další akce.',
    extractItems: extractEvents,
    extractHasMore,
    extractCount,
  });

  // Sticky cities — only the first page of each filter set returns them.
  useEffect(() => {
    const firstCities = firstPage?.cities || [];
    if (firstCities.length) setCities(firstCities);
  }, [firstPage]);

  const cityChoices = useMemo(
    () => ['Vše', ...cities.map((c) => c.name)],
    [cities],
  );

  // Visual split (server already filtered, this is purely for display).
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
        {isAdmin && (
          <Link to="/sprava/zpetna-vazba" className="admin-btn">📊 Zpětná vazba</Link>
        )}
      </section>

      {seasonChoices.length > 1 && (
        <section className="locations seasons">
          {seasonChoices.map((s) => (
            <button
              key={s.id}
              className={`loc${season === s.id ? ' on' : ''}`}
              onClick={() => setSeason(s.id)}
            >
              {s.name}
            </button>
          ))}
        </section>
      )}

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

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchEvents, fetchSeasons } from '../../services/api';
import { usePaginatedQuery } from '../../services/usePaginatedQuery';
import { useCachedQuery } from '../../services/queryCache';
import { useAuth } from '../../context/AuthContext';
import { CACHE_TTL, PAGE_SIZE_EVENTS, SEARCH_DEBOUNCE_MS } from '../../constants/config';
import EventCard from '../../components/EventCard/EventCard';
import PillTabs from '../../components/PillTabs/PillTabs';
import SearchInput from '../../components/SearchInput/SearchInput';
import PageHero from '../../components/PageHero/PageHero';
import { useReveal } from '../../hooks/useReveal';
import './EventsPage.css';

// Server response → local fields. Used by the pagination hook.
const extractEvents = (r) => r.events || [];
const extractHasMore = (r) => !!r.has_more;
const extractCount = (r) => r.count ?? 0;

export default function EventsPage() {
  const { isAdmin } = useAuth();
  const [city, setCity] = useState('Vše');
  const [season, setSeason] = useState('all'); // 'all' or a season id (as string)
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  // Cities are returned only on the first page; we keep them locally so
  // they survive filter changes.
  const [cities, setCities] = useState([]);

  // Season is now the primary filter (replaces the old upcoming/past/all tabs).
  // Tab keys are strings; 'all' = every season.
  const { data: seasonsData } = useCachedQuery('seasons', fetchSeasons, { ttl: CACHE_TTL.LEADERBOARD });
  const seasonTabs = useMemo(
    () => [{ key: 'all', label: 'Vše' }, ...(seasonsData?.seasons || []).map((s) => ({ key: String(s.id), label: s.name }))],
    [seasonsData],
  );

  // Reset city when season changes — the selected city may not exist in the
  // new season, producing a silent empty result that looks like "no events".
  const handleSeasonChange = useCallback((newSeason) => {
    setSeason(newSeason);
    setCity('Vše');
  }, []);

  // Debounce search input so we don't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);

  // Build the per-request params from current filters.
  const buildParams = useCallback((offset, limit) => {
    const params = { limit, offset };
    if (city !== 'Vše') params.city = city;
    if (season !== 'all') params.season_id = season;
    if (debouncedQuery.trim()) params.q = debouncedQuery.trim();
    return params;
  }, [city, season, debouncedQuery]);

  // Cache key encodes the filter combo so going back to the same filters
  // hits cache instantly.
  const cacheKey = useMemo(
    () => `events:${city}|${season}|${debouncedQuery.trim()}`,
    [city, season, debouncedQuery],
  );

  const {
    items: events, hasMore, totalCount, loading, loadingMore, loadMore, firstPage, error, retry,
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

  // Update city list whenever a new first page arrives. We skip the update
  // only if firstPage hasn't resolved yet (undefined = still loading) to avoid
  // a flash of empty filters. Once the response is in, we always overwrite —
  // stale cities from a previous season must not persist.
  useEffect(() => {
    if (firstPage === undefined) return;
    setCities(firstPage.cities || []);
  }, [firstPage]);

  // All cities surface in the filter panel (even those with a single event) so
  // users see the full set of choices. Each chip shows its event count.
  const cityChoices = useMemo(() => {
    if (!cities.length) return [];
    return [{ name: 'Vše', count: null }, ...cities];
  }, [cities]);

  const activeFilterCount = (season !== 'all' ? 1 : 0)
    + (city !== 'Vše' ? 1 : 0)
    + (debouncedQuery.trim() ? 1 : 0);

  const [filtersOpen, setFiltersOpen] = useState(true);

  const handleResetFilters = useCallback(() => {
    setSeason('all');
    setCity('Vše');
    setQuery('');
    setDebouncedQuery('');
  }, []);

  // Czech plural for "akce": 1 → akce, 2-4 → akce, 0/5+ → akcí.
  const fmtCount = (n) => `${n} ${n >= 1 && n <= 4 ? 'akce' : 'akcí'}`;

  // Visual split (server already filtered, this is purely for display).
  const { upcoming, past } = useMemo(() => ({
    upcoming: events
      .filter((ev) => !ev.is_past)
      .sort((a, b) => new Date(a.date) - new Date(b.date)),
    past: events
      .filter((ev) => ev.is_past)
      .sort((a, b) => new Date(b.date) - new Date(a.date)),
  }), [events]);

  // "No results" vs. "load failed" are different states — a failed first page
  // must NOT masquerade as "Žádné akce nenalezeny." (which made transient
  // network/cold-start failures look like there were simply no events).
  const empty = !loading && !error && events.length === 0;

  const [retrying, setRetrying] = useState(false);
  const handleRetry = useCallback(() => {
    setRetrying(true);
    // A failed retry stays surfaced via the hook's `error`, so swallow the
    // rejection here to avoid an unhandled promise rejection.
    Promise.resolve(retry()).catch(() => {}).finally(() => setRetrying(false));
  }, [retry]);

  // Looser threshold so grids that load just at the viewport edge still reveal.
  const [upRef, upIn] = useReveal({ threshold: 0.01, rootMargin: '0px 0px 80px 0px' });
  const [pastRef, pastIn] = useReveal({ threshold: 0.01, rootMargin: '0px 0px 80px 0px' });

  return (
    <div className="events-page">
      <div className="stage" />
      <div className="grain" />

      <PageHero
        eyebrow="Kalendář · Sezóna 2025/26"
        title="Events"
        tagline="Kompletní seznam akcí. Od karaoke přes nahou míli, deskovky až po bruslení. Sbírej body, hraj život."
      />

      <section className="filterbar">
        <button
          type="button"
          className={`filter-toggle${filtersOpen ? ' open' : ''}`}
          onClick={() => setFiltersOpen((o) => !o)}
          aria-expanded={filtersOpen}
          aria-controls="filter-panel"
        >
          <span className="ft-ico" aria-hidden="true">⚙</span>
          <span>Filtry</span>
          {activeFilterCount > 0 && <span className="ft-badge">{activeFilterCount}</span>}
          <span className="ft-chev" aria-hidden="true">{filtersOpen ? '▴' : '▾'}</span>
        </button>
        <div className="filter-count-pill" aria-live="polite">
          {loading && events.length === 0
            ? '…'
            : <><span className="fc-num">{totalCount}</span><span className="fc-lab">{totalCount >= 1 && totalCount <= 4 ? 'akce' : 'akcí'}</span></>}
        </div>
      </section>

      {filtersOpen && (
        <section id="filter-panel" className="filter-panel">
          <div className="fp-group fp-search">
            <SearchInput
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Hledat akci…"
            />
          </div>

          <div className="fp-group">
            <div className="fp-label">Sezóna</div>
            <PillTabs tabs={seasonTabs} active={season} onChange={handleSeasonChange} />
          </div>

          {cityChoices.length > 1 && (
            <div className="fp-group">
              <div className="fp-label">Místo</div>
              <div className="fp-chips">
                {cityChoices.map((c) => (
                  <button
                    key={c.name}
                    type="button"
                    className={`loc${city === c.name ? ' on' : ''}`}
                    onClick={() => setCity(c.name)}
                  >
                    {c.name}
                    {c.count != null && <span className="loc-count">{c.count}</span>}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeFilterCount > 0 && (
            <div className="fp-footer">
              <button type="button" className="fp-reset" onClick={handleResetFilters}>
                × Resetovat filtry
              </button>
              <span className="fp-result">{fmtCount(totalCount)}</span>
            </div>
          )}
        </section>
      )}

      {isAdmin && (
        <section className="admin-row">
          <Link to="/akce/vytvorit" className="admin-btn create-btn">+ Vytvořit akci</Link>
          <Link to="/sprava/zpetna-vazba" className="admin-btn">Zpětná vazba</Link>
        </section>
      )}

      <main className="events-main">
        {loading && <div className="empty">Načítám akce…</div>}
        {empty && <div className="empty">Žádné akce nenalezeny.</div>}
        {error && (
          <div className="events-error">
            <p>Akce se nepodařilo načíst. Zkontroluj připojení a zkus to znovu.</p>
            <button type="button" className="loc" onClick={handleRetry} disabled={retrying}>
              {retrying ? 'Načítám…' : 'Zkusit znovu'}
            </button>
          </div>
        )}

        {upcoming.length > 0 && (
          <>
            <div className="group-label">Nadcházející</div>
            <div ref={upRef} className={`events-grid reveal-stagger${upIn ? ' in' : ''}`}>
              {upcoming.map((ev) => (
                <div key={ev.id} className={`ev-wrap${isAdmin && !ev.visible_to_users ? ' ev-hidden' : ''}`}>
                  <EventCard event={ev} theme="light" />
                  {isAdmin && !ev.visible_to_users && <span className="ev-hidden-badge">Skryto</span>}
                </div>
              ))}
            </div>
          </>
        )}
        {past.length > 0 && (
          <>
            <div className="group-label past">Proběhlo</div>
            <div ref={pastRef} className={`events-grid reveal-stagger${pastIn ? ' in' : ''}`}>
              {past.map((ev) => (
                <div key={ev.id} className={`ev-wrap${isAdmin && !ev.visible_to_users ? ' ev-hidden' : ''}`}>
                  <EventCard event={ev} theme="light" />
                  {isAdmin && !ev.visible_to_users && <span className="ev-hidden-badge">Skryto</span>}
                </div>
              ))}
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

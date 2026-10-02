import { useMemo, useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { fetchAdminFeedbacks, fetchSeasons } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { queryKeys } from '../../services/queryKeys';
import { CACHE_TTL } from '../../constants/config';
import { useAuth } from '../../context/AuthContext';
import PillTabs from '../../components/PillTabs/PillTabs';
import StatList from '../../components/StatList/StatList';
import PageHero from '../../components/PageHero/PageHero';
import PageStage from '../../components/PageStage/PageStage';
import PageState from '../../components/PageState/PageState';
import { fmtDate } from '../../utils/date';
import './FeedbacksPage.css';

// Ratings are 1-10; ten glyphs don't fit the column, so show the number with a
// single star as the unit marker.
const SOURCE_LABEL = { web: 'web', form: 'formulář' };

// Per-event feedback table: player · rating · comment (leaderboard structure).
const COLUMNS = [
  {
    key: 'user',
    className: 'fba-player',
    render: (f) => (
      <span title={`${f.user.attended_events} absolvovaných akcí · zdroj: ${SOURCE_LABEL[f.source] ?? f.source}`}>
        {f.user.name}
      </span>
    ),
  },
  {
    key: 'rating',
    className: 'fba-stars',
    render: (f) => <span aria-label={`${f.rating} z 10`}>★ {f.rating}/10</span>,
  },
  { key: 'comment', className: 'fba-comment', render: (f) => f.comment || <span className="fba-muted">—</span> },
];
const FB_GRID = 'minmax(110px,1fr) 124px 2fr';

// Mean rating of a set of feedbacks, to one decimal. Null when there is nothing
// to average, so the caller can skip the badge entirely.
const avgRating = (items) => {
  const nums = items.map((f) => f.rating).filter((r) => typeof r === 'number');
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
};

// Czech decimals use a comma.
const fmtAvg = (n) => n.toFixed(1).replace('.', ',');

// True if an event datetime falls within a season's (inclusive) date range.
const inSeason = (dateStr, s) => {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  return d >= new Date(s.start) && d <= new Date(`${s.end}T23:59:59`);
};

export default function FeedbacksPage() {
  const { user, loading: authLoading, isAdmin } = useAuth();
  const [params] = useSearchParams();
  const eventSlug = params.get('event');
  const [season, setSeason] = useState('all'); // 'all' or a season id (string)

  const { data, loading, error, refetch } = useCachedQuery(queryKeys.adminFeedbacks, fetchAdminFeedbacks, {
    enabled: isAdmin,
    ttl: 60 * 1000,
  });
  const { data: seasonsData } = useCachedQuery(queryKeys.seasons, fetchSeasons, { ttl: CACHE_TTL.LEADERBOARD });
  // Memoised, not `?? []`: a fresh [] each render gives every dependent
  // useMemo a new identity, so they all recompute on every render.
  const seasons = useMemo(() => seasonsData?.seasons || [], [seasonsData]);

  const seasonTabs = useMemo(
    () => [{ key: 'all', label: 'Vše' }, ...seasons.map((s) => ({ key: String(s.id), label: s.name }))],
    [seasons],
  );

  // Filter (deep-linked event, then season) → group by event, newest event first.
  const groups = useMemo(() => {
    const all = data?.feedbacks || [];
    let list = eventSlug ? all.filter((f) => f.event.slug === eventSlug) : all;
    if (season !== 'all') {
      const s = seasons.find((x) => String(x.id) === season);
      list = s ? list.filter((f) => inSeason(f.event.date, s)) : [];
    }
    const map = new Map();
    for (const f of list) {
      const key = f.event.slug;
      if (!map.has(key)) map.set(key, { event: f.event, items: [] });
      map.get(key).items.push(f);
    }
    return [...map.values()]
      .map((g) => ({ ...g, avg: avgRating(g.items) }))
      .sort((a, b) => new Date(b.event.date) - new Date(a.event.date));
  }, [data, eventSlug, season, seasons]);

  if (authLoading) return null;
  if (!user || !isAdmin) return <Navigate to="/" replace />;

  const eventName = eventSlug ? groups[0]?.event?.name : null;

  return (
    <div className="feedbacks-page has-stage">
      <PageStage image="gal2" position="center 28%" tint="calm" grain="blue" />

      <PageHero
        eyebrow="Admin"
        title="Zpětná vazba"
        tagline={eventName || undefined}
      />

      <main className="fba-main">
        {!eventSlug && seasons.length > 0 && (
          <div className="fba-controls">
            <PillTabs tabs={seasonTabs} active={season} onChange={setSeason} />
          </div>
        )}

        {loading && groups.length === 0 ? (
          <PageState kind="loading" text="Načítám zpětnou vazbu…" />
        ) : error && groups.length === 0 ? (
          <PageState kind="error" text="Zpětnou vazbu se nepodařilo načíst. Zkus to znovu." onRetry={refetch} busy={loading} />
        ) : groups.length === 0 ? (
          <PageState kind="empty" text="Zatím žádná zpětná vazba." />
        ) : (
          groups.map((g) => (
            <section className="fba-group" key={g.event.slug}>
              <div className="fba-event-head">
                <div className="fba-event-id">
                  <Link to={`/events/${g.event.slug}`} className="fba-event-name">{g.event.name}</Link>
                  <div className="fba-event-date">{fmtDate(g.event.date) || '—'}</div>
                </div>
                {g.avg !== null && (
                  <div className="fba-avg" title={`Průměr z ${g.items.length} hodnocení`}>
                    <div className="fba-avg-score"><span className="fba-avg-star">★</span> {fmtAvg(g.avg)}<span className="fba-avg-max">/10</span></div>
                    <div className="fba-avg-label">průměr · {g.items.length} hodnocení</div>
                  </div>
                )}
              </div>
              <StatList
                className="poster"
                columns={COLUMNS}
                rows={g.items}
                gridTemplate={FB_GRID}
                rowKey={(f) => f.id}
              />
            </section>
          ))
        )}
      </main>
    </div>
  );
}

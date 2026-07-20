import { useMemo, useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { fetchAdminFeedbacks, fetchSeasons } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { useAuth } from '../../context/AuthContext';
import PillTabs from '../../components/PillTabs/PillTabs';
import StatList from '../../components/StatList/StatList';
import { fmtDate } from '../../utils/date';
import './FeedbacksPage.css';

// Ratings are 1-10; ten glyphs don't fit the column, so show the number with a
// single star as the unit marker.
const SOURCE_LABEL = { web: 'web', form: 'formulář' };

// Per-event feedback table: player · rating · comment (leaderboard structure).
const COLUMNS = [
  {
    key: 'user',
    className: 'fb-player',
    render: (f) => (
      <span title={`${f.user.attended_events} absolvovaných akcí · zdroj: ${SOURCE_LABEL[f.source] ?? f.source}`}>
        {f.user.name}
      </span>
    ),
  },
  {
    key: 'rating',
    className: 'fb-stars',
    render: (f) => <span aria-label={`${f.rating} z 10`}>★ {f.rating}/10</span>,
  },
  { key: 'comment', className: 'fb-comment', render: (f) => f.comment || <span className="fb-muted">—</span> },
];
const FB_GRID = 'minmax(110px,1fr) 124px 2fr';

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

  const { data, loading } = useCachedQuery('admin:feedbacks', fetchAdminFeedbacks, {
    enabled: isAdmin,
    ttl: 60 * 1000,
  });
  const { data: seasonsData } = useCachedQuery('seasons', fetchSeasons, { ttl: 5 * 60 * 1000 });
  const seasons = seasonsData?.seasons || [];

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
    return [...map.values()].sort((a, b) => new Date(b.event.date) - new Date(a.event.date));
  }, [data, eventSlug, season, seasons]);

  if (authLoading) return null;
  if (!user || !isAdmin) return <Navigate to="/" replace />;

  const eventName = eventSlug ? groups[0]?.event?.name : null;

  return (
    <div className="feedbacks-page">
      <div className="stage" />
      <div className="grain" />

      <header className="fb-head">
        <div className="fb-eyebrow">— Admin —</div>
        <h1>Zpětná vazba{eventName ? ` · ${eventName}` : ''}</h1>
      </header>

      <main className="fb-main">
        {!eventSlug && seasons.length > 0 && (
          <div className="fb-controls">
            <PillTabs tabs={seasonTabs} active={season} onChange={setSeason} />
          </div>
        )}

        {loading && groups.length === 0 ? (
          <div className="fb-status">Načítám…</div>
        ) : groups.length === 0 ? (
          <div className="fb-status">Zatím žádná zpětná vazba.</div>
        ) : (
          groups.map((g) => (
            <section className="fb-group" key={g.event.slug}>
              <div className="fb-event-head">
                <Link to={`/events/${g.event.slug}`} className="fb-event-name">{g.event.name}</Link>
                <div className="fb-event-date">{fmtDate(g.event.date) || '—'}</div>
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

import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { fetchAdminFeedbacks } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { useAuth } from '../../context/AuthContext';
import Table from '../../components/Table/Table';
import { fmtDate } from '../../utils/date';
import './FeedbacksPage.css';

const STARS = (n) => '★'.repeat(n) + '☆'.repeat(Math.max(0, 5 - n));

const COLUMNS = [
  {
    key: 'event',
    label: 'Akce',
    render: (event) => (
      <Link to={`/akce/${event.slug}`} className="fb-event-link">{event.name}</Link>
    ),
  },
  {
    key: 'user',
    label: 'Hráč',
    render: (user) => (
      <span title={`${user.attended_events} absolvovaných akcí`}>{user.name}</span>
    ),
  },
  {
    key: 'rating',
    label: 'Hodnocení',
    align: 'center',
    render: (rating) => <span className="fb-stars" aria-label={`${rating} z 5`}>{STARS(rating)}</span>,
  },
  { key: 'comment', label: 'Komentář', render: (c) => c || <span className="fb-muted">—</span> },
  { key: 'updated_at', label: 'Datum', align: 'right', render: (d) => fmtDate(d) },
];

export default function FeedbacksPage() {
  const { user, loading: authLoading, isAdmin } = useAuth();
  const [params] = useSearchParams();
  const eventSlug = params.get('event');
  const { data, loading } = useCachedQuery('admin:feedbacks', fetchAdminFeedbacks, {
    enabled: isAdmin,
    ttl: 60 * 1000,
  });

  if (authLoading) return null;
  if (!user || !isAdmin) return <Navigate to="/" replace />;

  const all = data?.feedbacks || [];
  const feedbacks = eventSlug ? all.filter((f) => f.event.slug === eventSlug) : all;
  const eventName = eventSlug ? feedbacks[0]?.event?.name : null;

  return (
    <div className="feedbacks-page">
      <header className="fb-head">
        <div className="fb-eyebrow">— Admin —</div>
        <h1>Zpětná vazba{eventName ? ` · ${eventName}` : ''}</h1>
        <p className="fb-sub">
          {eventSlug
            ? <>Hodnocení této akce. <Link to="/sprava/zpetna-vazba" className="fb-event-link">Zobrazit vše →</Link></>
            : 'Hodnocení a komentáře k akcím od hráčů.'}
        </p>
      </header>
      <main className="fb-main">
        {loading && feedbacks.length === 0
          ? <div className="fb-status">Načítám…</div>
          : (
            <Table
              columns={COLUMNS}
              rows={feedbacks}
              emptyText="Zatím žádná zpětná vazba."
            />
          )}
      </main>
    </div>
  );
}

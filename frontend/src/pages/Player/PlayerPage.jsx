import { Link, Navigate, useParams } from 'react-router-dom';
import { fetchPlayer } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import Avatar from '../../components/Avatar/Avatar';
import Table from '../../components/Table/Table';
import { fmtDate } from '../../utils/date';
import './PlayerPage.css';

// Attended-events table (newest first). Reuses the shared <Table> styled with
// the blue grain texture, matching the leaderboard's visual language.
const COLUMNS = [
  { key: 'category', label: 'Kategorie', render: (c) => c?.name || 'Akce' },
  {
    key: 'name',
    label: 'Akce',
    render: (name, row) => <Link to={`/akce/${row.slug}`} className="pl-link">{name}</Link>,
  },
  { key: 'place', label: 'Místo' },
  { key: 'date', label: 'Datum', align: 'right', render: (d) => fmtDate(d) },
  { key: 'points', label: 'Body', align: 'right', render: (p) => `+${p}` },
];

// Public view for a leaderboard player by id. Registered players (those with an
// account) are redirected to their full /profil/ page; this renders the rest
// (Google-Sheets players with no account).
export default function PlayerPage() {
  const { userId } = useParams();
  const { data: player, loading, error } = useCachedQuery(
    `player:${userId}`,
    () => fetchPlayer(userId),
    { enabled: !!userId, ttl: CACHE_TTL.PROFILE },
  );

  if (player?.profile_username) {
    return <Navigate to={`/profil/${player.profile_username}`} replace />;
  }

  if (loading && !player) {
    return (
      <div className="player-page">
        <div className="stage" />
        <div className="grain" />
        <div className="player-status">Načítám hráče…</div>
      </div>
    );
  }
  if (error || !player) {
    const msg = error?.response?.status === 404 ? 'Hráč nenalezen.' : 'Nepodařilo se načíst hráče.';
    return (
      <div className="player-page">
        <div className="stage" />
        <div className="grain" />
        <div className="player-status">{msg}</div>
        <div className="player-back"><Link to="/leaderboard">← Zpět na leaderboard</Link></div>
      </div>
    );
  }

  return (
    <div className="player-page">
      <div className="stage" />
      <div className="grain" />

      <header className="player-hero">
        <div className="player-eyebrow">Hráč · Game of Life</div>
        <Avatar name={player.name} size="xl" className="player-avatar" />
        <h1 className="player-name">{player.name}</h1>
        <div className="player-stats">
          <div className="player-stat">
            <div className="player-stat-val">{player.rank ? `#${player.rank}` : '—'}</div>
            <div className="player-stat-label">Pozice</div>
          </div>
          <div className="player-stat">
            <div className="player-stat-val">{player.total_points}</div>
            <div className="player-stat-label">Bodů</div>
          </div>
          <div className="player-stat">
            <div className="player-stat-val">{player.events_count}</div>
            <div className="player-stat-label">Akcí</div>
          </div>
        </div>
        <p className="player-note">Tento hráč zatím nemá účet na webu.</p>
        <div className="player-divider" />
      </header>

      <main className="player-main">
        <div className="player-list-label">Absolvované akce</div>
        <Table
          className="pl-table"
          columns={COLUMNS}
          rows={player.events || []}
          emptyText="Žádné zaznamenané akce."
        />
      </main>

      <div className="player-back">
        <Link to="/leaderboard">← Zpět na leaderboard</Link>
      </div>
    </div>
  );
}

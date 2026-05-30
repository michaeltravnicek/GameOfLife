import { useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { fetchPlayer, fetchPlayerSeason } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import PillTabs from '../../components/PillTabs/PillTabs';
import StatList from '../../components/StatList/StatList';
import { EVENT_COLUMNS } from '../../components/StatList/eventColumns';
import './PlayerPage.css';

// Public view for a leaderboard player by id. Registered players (those with an
// account) are redirected to their full /profil/ page; this renders the rest
// (Google-Sheets players with no account), with per-season stats like profiles.
export default function PlayerPage() {
  const { userId } = useParams();
  const [pickedSeason, setPickedSeason] = useState(null); // explicit season pick (id)

  const { data: player, loading, error } = useCachedQuery(
    `player:${userId}`,
    () => fetchPlayer(userId),
    { enabled: !!userId, ttl: CACHE_TTL.PROFILE },
  );

  const seasons = player?.seasons || [];
  const hasSeasons = seasons.length > 0;
  // Selected season = explicit pick, else the newest season (same as profiles).
  const seasonKey = pickedSeason ?? seasons[0]?.id ?? null;

  // Lazy per-season detail (event list + points + rank) for the chosen season.
  const { data: seasonDetail } = useCachedQuery(
    `player:${userId}:season:${seasonKey}`,
    () => fetchPlayerSeason(userId, seasonKey),
    { enabled: !!userId && seasonKey != null, ttl: CACHE_TTL.PROFILE },
  );
  const summary = hasSeasons ? (seasons.find((s) => s.id === seasonKey) || seasons[0]) : null;
  const seasonData = (seasonDetail && seasonDetail.id === seasonKey) ? seasonDetail : summary;

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

  // Stats + events reflect the selected season; fall back to all-time when the
  // player has no leaderboard seasons.
  const events = hasSeasons ? (seasonData?.events || []) : (player.events || []);
  const statRank = hasSeasons ? seasonData?.rank : player.rank;
  const statPoints = hasSeasons ? (seasonData?.season_pts ?? 0) : player.total_points;
  const statEvents = hasSeasons ? events.length : player.events_count;
  const seasonTabs = seasons.map((s) => ({ key: s.id, label: s.label }));

  return (
    <div className="player-page">
      <div className="stage" />
      <div className="grain" />

      <header className="player-hero">
        <div className="player-badges">
          {statRank && <span className="player-pill live">★ #{statRank} Leaderboard</span>}
          {summary?.label && <span className="player-pill">Sezóna {summary.label}</span>}
        </div>
        <h1 className="player-name">{player.name}</h1>
        <div className="player-handle">Hráč · Game of Life</div>

        {/* Stats rendered as big "credits" over the photo, like the profile poster. */}
        <div className="player-credits">
          <span className="player-credits-rule" />
          <div className="player-credit">
            <div className="player-credit-label">— Body —</div>
            <div className="player-credit-value">{statPoints ?? 0}</div>
            <div className="player-credit-sub">{hasSeasons ? 'v sezóně' : 'celkem'}</div>
          </div>
          <div className="player-credit">
            <div className="player-credit-label">— Akcí —</div>
            <div className="player-credit-value">{statEvents ?? 0}</div>
            <div className="player-credit-sub">absolvováno</div>
          </div>
          <div className="player-credit">
            <div className="player-credit-label">— Pozice —</div>
            <div className="player-credit-value">{statRank ? `#${statRank}` : '—'}</div>
            <div className="player-credit-sub">{statRank ? 'v žebříčku' : 'zatím bez bodů'}</div>
          </div>
        </div>

        <p className="player-note">Tento hráč zatím nemá účet na webu.</p>
      </header>

      <main className="player-main">
        {hasSeasons && (
          <div className="player-seasons">
            <PillTabs tabs={seasonTabs} active={seasonKey} onChange={setPickedSeason} />
          </div>
        )}
        <div className="player-list-label">Absolvované akce</div>
        <StatList
          className="ev-grid"
          columns={EVENT_COLUMNS}
          rows={events}
          rowKey={(e) => e.slug}
          rowLink={(e) => `/akce/${e.slug}`}
          rowClass={() => 'past'}
          emptyText="Žádné zaznamenané akce v této sezóně."
        />
      </main>

      <div className="player-back">
        <Link to="/leaderboard">← Zpět na leaderboard</Link>
      </div>
    </div>
  );
}

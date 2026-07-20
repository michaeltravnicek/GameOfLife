import { useMemo, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import PillTabs from '../../components/PillTabs/PillTabs';
import Button from '../../components/Button/Button';
import { useSeasonView } from '../Profile/useSeasonView';
import { ProfileCredits, EventsSections, PointsSections } from '../Profile/profileSections';
import { fetchPlayer, fetchPlayerSeason } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import { shareLink } from '../../utils/shareUrl';
import { initials } from '../../utils/name';
import '../Profile/ProfilePage.css';
import './PlayerPage.css';

const TODAY = new Date();

// Anonymous profile for a leaderboard player by id — Google-Sheets players who
// have no account yet. Renders the same poster/credits/tabs skin as the full
// ProfilePage (ProfilePage.css), minus everything identity-owned: no "O mně"
// tab (no bio/city/socials/photo), an unclaimed avatar, and a claim CTA.
// Registered players are redirected to their /profil/ page.
export default function PlayerPage() {
  const { userId } = useParams();
  const [pickedSeason, setPickedSeason] = useState(null); // explicit season pick (id)
  const [view, setView] = useState('events');

  const { data: player, loading: playerLoading, error: playerError } = useCachedQuery(
    `player:${userId}`,
    () => fetchPlayer(userId),
    { enabled: !!userId, ttl: CACHE_TTL.PROFILE },
  );

  // Selected season = explicit pick, else the newest season (same as profiles).
  const seasonKey = pickedSeason ?? player?.seasons?.[0]?.id ?? null;

  // Lazy per-season detail (event list + points + rank) for the chosen season.
  const { data: seasonDetail } = useCachedQuery(
    `player:${userId}:season:${seasonKey}`,
    () => fetchPlayerSeason(userId, seasonKey),
    { enabled: !!userId && seasonKey != null, ttl: CACHE_TTL.PROFILE },
  );

  const summary = useMemo(() => {
    if (!player) return null;
    const seasons = player.seasons || [];
    if (seasons.length) return seasons.find((s) => s.id === seasonKey) || seasons[0];
    // No leaderboard seasons — synthesize one from the all-time payload so the
    // poster/chart still render. All-time events carry `points`, not `pts`, and
    // may span years, so the span stretches from the first event to today.
    const evs = (player.events || []).map((e) => ({ ...e, pts: e.pts ?? e.points }));
    const dates = evs.map((e) => new Date(e.date).getTime());
    const start = dates.length ? new Date(Math.min(...dates)) : new Date(TODAY.getFullYear(), 0, 1);
    const end = new Date(Math.max(TODAY.getTime(), ...dates));
    return {
      id: null,
      label: 'Celkem',
      start: start.toISOString(),
      end: end.toISOString(),
      season_pts: player.total_points || 0,
      rank: player.rank || null,
      events: evs,
    };
  }, [player, seasonKey]);
  // Prefer the detail (has events) for the current season; fall back to the
  // summary so the poster renders immediately while detail loads.
  const seasonData = (seasonDetail && seasonDetail.id === seasonKey) ? seasonDetail : summary;
  // Shared derivation (stats + sorted event lists + category breakdown). Runs
  // unconditionally and tolerates a null seasonData, so it stays above the
  // early returns and keeps the hook count stable across renders.
  const { st, upcoming, past, cats } = useSeasonView(seasonData, TODAY);

  // Players with a linked account get the full profile instead.
  if (player?.profile_username) {
    return <Navigate to={`/profil/${player.profile_username}`} replace />;
  }

  if (playerLoading && !player) return <div className="profile-page player-anon"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítám hráče…</div></div>;
  if (playerError) {
    const msg = playerError.response?.status === 404 ? 'Hráč nenalezen' : 'Nepodařilo se načíst hráče';
    return <div className="profile-page player-anon"><div style={{ padding: '2rem', textAlign: 'center', color: '#e15463' }}>Chyba: {msg}</div></div>;
  }
  if (!player || !st) return <div className="profile-page player-anon"><div style={{ padding: '2rem', textAlign: 'center' }}>Hráč nenalezen</div></div>;

  const avatarInitials = initials(player.name, '?');

  const handleShare = () => shareLink(`${player.name} — Game of Life`);

  const seasonTabs = player.seasons?.map((s) => ({ key: s.id, label: s.label })) || [];
  const viewTabs = [
    { key: 'events', label: 'Akce', badge: st.evs.length },
    { key: 'points', label: 'Body', badge: st.totalPts },
  ];

  return (
    <div className="profile-page player-anon">
      <section className="poster">
        <div className="poster-img" />
        <div className="poster-grain" />
        <div className="poster-vignette" />

        <div className="poster-top">
          <div className="badges">
            {st.rank && <span className="ev-pill live">★ #{st.rank} Leaderboard</span>}
            <span className="ev-pill">Sezóna {st.label}</span>
          </div>
          <div className="poster-avatar">{avatarInitials}</div>
          <h1 className="poster-name">{player.name}</h1>
          <div className="poster-handle">hráč Game of Life · profil bez účtu</div>
        </div>

        <ProfileCredits st={st} />
      </section>

      <div className="action-bar">
        <div className="action-inner">
          <PillTabs tabs={seasonTabs} active={seasonKey} onChange={setPickedSeason} />
          <PillTabs tabs={viewTabs} active={view} onChange={setView} />
        </div>
      </div>

      <div className="body-wrap">
        <main className="profile-main">
          <section className="profile-view" key={view}>
            {view === 'events' && (
              <EventsSections st={st} upcoming={upcoming} past={past} startNum={1} />
            )}

            {view === 'points' && (
              <PointsSections st={st} cats={cats} today={TODAY} startNum={3} />
            )}
          </section>
        </main>
      </div>

      <div className="back-strip">
        <div className="back-strip-inner">
          {/* Navigation = 3D buttons (frost for "back"); round pills = in-place actions. */}
          <Button as="link" to="/leaderboard" variant="frost">← Zpět na leaderboard</Button>
          <div className="back-actions">
            <span className="claim-note">Jsi to ty? Založ si účet a převezmi svůj profil.</span>
            <Button as="link" to="/registrace">Založit účet</Button>
            <Button variant="ghost" onClick={handleShare}>Sdílet profil</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

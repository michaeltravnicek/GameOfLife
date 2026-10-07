import { useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import PillTabs from '../../components/PillTabs/PillTabs';
import Button from '../../components/Button/Button';
import PageState from '../../components/PageState/PageState';
import { TODAY, useProfileSeason } from '../Profile/useSeasonView';
import { ProfilePoster, EventsSections, PointsSections } from '../Profile/profileSections';
import { fetchPlayer, fetchPlayerSeason } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { queryKeys } from '../../services/queryKeys';
import { CACHE_TTL } from '../../constants/config';
import { shareLink } from '../../utils/shareUrl';
import { initials } from '../../utils/name';
import '../../styles/poster-hero.css';
import '../Profile/ProfilePage.css';
import './PlayerPage.css';

// No leaderboard seasons — synthesize one from the all-time payload so the
// poster/chart still render. All-time events carry `points`, not `pts`, and may
// span years, so the span stretches from the first event to today.
function allTimeSummary(player) {
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
}

// Anonymous profile for a leaderboard player by id — Google-Sheets players who
// have no account yet. Renders the same poster/credits/tabs skin as the full
// ProfilePage (ProfilePage.css), minus everything identity-owned: no "O mně"
// tab (no bio/city/socials/photo), an unclaimed avatar, and a claim CTA.
// Registered players are redirected to their /profil/ page.
export default function PlayerPage() {
  const { userId } = useParams();
  const { user } = useAuth();
  const [view, setView] = useState('events');

  const { data: player, loading: playerLoading, error: playerError } = useCachedQuery(
    queryKeys.player(userId),
    () => fetchPlayer(userId),
    { enabled: !!userId, ttl: CACHE_TTL.PROFILE },
  );

  // Runs unconditionally and tolerates a null player, so it stays above the
  // early returns and keeps the hook count stable across renders.
  const { seasonKey, setPickedSeason, seasonTabs, st, upcoming, past, cats } = useProfileSeason(
    player,
    {
      key: (seasonId) => queryKeys.player(userId, seasonId),
      fetch: (seasonId) => fetchPlayerSeason(userId, seasonId),
      enabled: !!userId,
    },
    allTimeSummary,
  );

  // Players with a linked account get the full profile instead.
  if (player?.profile_username) {
    return <Navigate to={`/profil/${player.profile_username}`} replace />;
  }
  // A merged-away id: the API answers with the player it was merged into.
  if (player && String(player.id) !== userId) {
    return <Navigate to={`/hrac/${player.id}`} replace />;
  }

  if (playerLoading && !player) return <div className="profile-page player-anon"><PageState kind="loading" fill text="Načítám hráče…" /></div>;
  if (playerError) {
    const notFound = playerError.response?.status === 404;
    return (
      <div className="profile-page player-anon">
        <PageState kind={notFound ? 'empty' : 'error'} fill text={notFound ? 'Hráč nenalezen.' : 'Hráče se nepodařilo načíst.'} />
      </div>
    );
  }
  if (!player || !st) return <div className="profile-page player-anon"><PageState kind="empty" fill text="Hráč nenalezen." /></div>;

  const avatarInitials = initials(player.name, '?');

  const handleShare = () => shareLink(`${player.name} — Game of Life`);

  // See ProfilePage: withheld sections are absent, not zero, so their tabs go.
  const hidden = player.hidden || [];
  const viewTabs = [
    !hidden.includes('events') && { key: 'events', label: 'Akce', badge: st.evs.length },
    !hidden.includes('points') && { key: 'points', label: 'Body', badge: st.totalPts },
  ].filter(Boolean);
  // The default view ('events') may be one of the hidden ones, which would leave
  // the body blank. Fall back to whatever tab still exists.
  const activeView = viewTabs.some((t) => t.key === view) ? view : (viewTabs[0]?.key ?? null);

  return (
    <div className="profile-page player-anon">
      <ProfilePoster
        st={st}
        hidden={hidden}
        avatar={avatarInitials}
        name={player.name}
        handle="hráč Game of Life · profil bez účtu"
      />

      <div className="action-bar">
        <div className="action-inner">
          <PillTabs tabs={seasonTabs} active={seasonKey} onChange={setPickedSeason} />
          <PillTabs tabs={viewTabs} active={activeView} onChange={setView} />
        </div>
      </div>

      <div className="poster-body">
        <main className="profile-main">
          <section className="profile-view" key={activeView}>
            {activeView === 'events' && (
              <EventsSections st={st} upcoming={upcoming} past={past} startNum={1} />
            )}

            {activeView === 'points' && (
              <PointsSections st={st} cats={cats} today={TODAY} startNum={3} />
            )}

            {!activeView && (
              <p className="profile-hidden-note">
                Tento hráč si své body i akce nechává pro sebe.
              </p>
            )}
          </section>
        </main>
      </div>

      <div className="back-strip">
        <div className="back-strip-inner">
          {/* Navigation = 3D buttons (frost for "back"); round pills = in-place actions. */}
          <Button as="link" to="/leaderboard" variant="frost">← Zpět na leaderboard</Button>
          <div className="back-actions">
            {/* Claiming is an admin merge (leaderboard/merging.py), so a member
                who already has an account cannot do it from here. */}
            {user ? (
              <span className="claim-note">Jsi to ty? Napiš organizátorům a připojí tuhle historii k tvému účtu.</span>
            ) : (
              <>
                <span className="claim-note">Jsi to ty? Založ si účet a převezmi svůj profil.</span>
                <Button as="link" to="/registrace">Založit účet</Button>
              </>
            )}
            <Button variant="ghost" onClick={handleShare}>Sdílet profil</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

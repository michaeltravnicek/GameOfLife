import { useMemo, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import PillTabs from '../../components/PillTabs/PillTabs';
import TicketList from '../../components/StatList/TicketList';
import { EVENT_COLUMNS, EVENT_LIST_CLASS } from '../../components/StatList/eventColumns';
import Button from '../../components/Button/Button';
import { TicketFrame } from '../../components/DashedBorder/DashedBorder';
import PointsChart from '../Profile/PointsChart';
import { seasonStats } from '../Profile/seasonStats';
import { fetchPlayer, fetchPlayerSeason } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import { shareLink } from '../../utils/shareUrl';
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
  const st = useMemo(() => (seasonData ? seasonStats(seasonData, TODAY) : null), [seasonData]);

  // All hooks stay above the early returns (stable hook count across renders).
  const upcoming = useMemo(
    () => (st ? st.future.slice().sort((a, b) => new Date(a.date) - new Date(b.date)) : []),
    [st],
  );
  const past = useMemo(
    () => (st ? st.past.slice().sort((a, b) => new Date(b.date) - new Date(a.date)) : []),
    [st],
  );

  const cats = useMemo(() => {
    if (!st) return { sorted: [], max: 1 };
    const buckets = {};
    st.evs.forEach((e) => {
      // Only real categories — uncategorized events don't form a fake bucket,
      // and the whole section hides when nothing remains.
      const cat = e.category?.name;
      if (!cat) return;
      if (!buckets[cat]) buckets[cat] = { n: 0, p: 0 };
      buckets[cat].n += 1;
      buckets[cat].p += e.pts;
    });
    const sorted = Object.entries(buckets).sort((a, b) => b[1].p - a[1].p);
    const max = Math.max(...sorted.map(([, b]) => b.p), 1);
    return { sorted, max };
  }, [st]);

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

  const initials = (player.name || '').split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';

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
          <div className="poster-avatar">{initials}</div>
          <h1 className="poster-name">{player.name}</h1>
          <div className="poster-handle">hráč Game of Life · profil bez účtu</div>
        </div>

        <div className="credits">
          <span className="credits-rule" />
          <div className="credit">
            <div className="credit-label">— Body —</div>
            <div className="credit-value">{st.totalPts}</div>
            <div className="credit-sub"><strong>{st.cities.length} měst</strong> · {st.future.length ? 'aktivní sezóna' : 'sezóna ukončena'}</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Akcí —</div>
            <div className="credit-value">{st.evs.length}</div>
            <div className="credit-sub"><strong>{st.past.length} absolv.</strong> · {st.future.length} nadch.</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Pozice —</div>
            <div className="credit-value">{st.rank ? `#${st.rank}` : '—'}</div>
            <div className="credit-sub">{st.rank ? 'v sezóně' : 'zatím bez bodů'}</div>
          </div>
        </div>
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
              <>
                {upcoming.length > 0 && (
                  <div className="section">
                    <div className="sec-rule" />
                    <div className="sec-eyebrow"><span>— 01 · Nadcházející —</span><span className="meta">+{st.futurePts} pts na cestě</span></div>
                    <h2 className="sec-heading">Co ho <span className="pink">čeká.</span></h2>
                    <TicketList
                      className={EVENT_LIST_CLASS}
                      columns={EVENT_COLUMNS}
                      rows={upcoming}
                      rowKey={(e) => e.slug}
                      rowLink={(e) => `/events/${e.slug}`}
                      rowClass={() => 'future'}
                    />
                  </div>
                )}

                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 02 · Absolvované —</span><span className="meta">+{st.pastPts} pts zatím</span></div>
                  <h2 className="sec-heading">Co má <span className="pink">za sebou.</span></h2>
                  <TicketList
                    className={EVENT_LIST_CLASS}
                    columns={EVENT_COLUMNS}
                    rows={past}
                    rowKey={(e) => e.slug}
                    rowLink={(e) => `/events/${e.slug}`}
                    rowClass={() => 'past'}
                    emptyText="Zatím žádné absolvované akce v této sezóně."
                  />
                </div>
              </>
            )}

            {view === 'points' && (
              <>
                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 03 · Body v čase —</span><span className="meta">křivka sezóny</span></div>
                  <h2 className="sec-heading">Křivka <span className="pink">sezóny.</span></h2>

                  <div className="chart-card">
                    <TicketFrame />
                    <div className="chart-in">
                      <div className="chart-meta">
                        <div>
                          <div className="l">Celkem v sezóně</div>
                          <div className="total">{st.totalPts}<small>pts</small></div>
                        </div>
                        <div className="legend">
                          <span><i />Absolvováno</span>
                          <span><i className="dashed" />Nadcházející</span>
                          <span style={{ color: '#f5c842' }}><i style={{ background: '#f5c842' }} />Dnes</span>
                        </div>
                      </div>
                      <PointsChart stats={st} today={TODAY} />
                    </div>
                  </div>
                </div>

                {cats.sorted.length > 0 && (
                  <div className="section">
                    <div className="sec-rule" />
                    <div className="sec-eyebrow"><span>— 04 · Kategorie —</span><span className="meta">{cats.sorted.length} kategorií</span></div>
                    <h2 className="sec-heading">V čem <span className="pink">jede.</span></h2>
                    <div className="cat-list">
                      {cats.sorted.map(([cat, b]) => (
                        <div className="cat-row" key={cat}>
                          <span className="name">{cat}</span>
                          <span className="bar"><i style={{ width: `${Math.round((b.p / cats.max) * 100)}%` }} /></span>
                          <span className="meta">{b.n}× · <b>+{b.p}</b></span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
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

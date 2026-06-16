import { useMemo, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import PillTabs from '../../components/PillTabs/PillTabs';
import StatList from '../../components/StatList/StatList';
import { EVENT_COLUMNS, EVENT_LIST_CLASS } from '../../components/StatList/eventColumns';
import Button from '../../components/Button/Button';
import PointsChart from './PointsChart';
import { fetchProfile, fetchProfileSeason } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { useAuth } from '../../context/AuthContext';
import { CACHE_TTL } from '../../constants/config';
import { shareLink } from '../../utils/shareUrl';
import './ProfilePage.css';

const TODAY = new Date();

function seasonStats(season, today) {
  // `season` may be a lightweight summary (no events, just season_pts) or the
  // full detail (with events). When events are present we derive everything from
  // them; otherwise we fall back to the summary's season_pts so the poster shows
  // the right total while the event list lazy-loads.
  const evs = [...(season.events || [])].sort((a, b) => new Date(a.date) - new Date(b.date));
  const past = evs.filter((e) => new Date(e.date) < today);
  const future = evs.filter((e) => new Date(e.date) >= today);
  const totalPts = evs.length ? evs.reduce((a, e) => a + e.pts, 0) : (season.season_pts || 0);
  const pastPts = past.reduce((a, e) => a + e.pts, 0);
  const futurePts = future.reduce((a, e) => a + e.pts, 0);
  const cities = [...new Set(evs.map((e) => e.place))];
  const rank = season.rank || (totalPts > 0 ? '—' : null);
  return { evs, past, future, totalPts, pastPts, futurePts, cities, start: new Date(season.start), end: new Date(season.end), label: season.label, rank };
}

export default function ProfilePage() {
  const { username } = useParams();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const [pickedSeason, setPickedSeason] = useState(null); // user's explicit pick (season id)
  const [view, setView] = useState('about');

  // Core profile (stats, rank, upcoming RSVPs, season summaries — no events).
  const { data: profile, loading: profileLoading, error: profileError } = useCachedQuery(
    `profile:${username}`,
    () => fetchProfile(username),
    { enabled: !!username, ttl: CACHE_TTL.PROFILE },
  );

  // Selected season = the user's pick, else the newest season. Derived (no
  // effect) so it's correct on the same render the profile arrives — no flash.
  const seasonKey = pickedSeason ?? profile?.seasons?.[0]?.id ?? null;

  // Lazy per-season detail (the event list + points that feed the chart). The
  // core payload only carries lightweight summaries, so we fetch this on demand
  // whenever the selected season changes.
  const { data: seasonDetail } = useCachedQuery(
    `profile:${username}:season:${seasonKey}`,
    () => fetchProfileSeason(username, seasonKey),
    { enabled: !!username && seasonKey != null, ttl: CACHE_TTL.PROFILE },
  );

  const summary = useMemo(() => {
    if (!profile) return null;
    const seasons = profile.seasons || [];
    if (seasons.length) return seasons.find((s) => s.id === seasonKey) || seasons[0];
    // No leaderboard seasons for this user — synthesize one from the profile
    // totals so the page still renders (header / about / socials) instead of
    // collapsing to "Profil nenalezen".
    const y = TODAY.getFullYear();
    return {
      id: null,
      label: 'Celkem',
      start: new Date(y, 0, 1).toISOString(),
      end: new Date(y, 11, 31).toISOString(),
      season_pts: profile.total_points || 0,
      rank: profile.rank || null,
      events: [],
    };
  }, [profile, seasonKey]);
  // Prefer the detail (has events) for the current season; fall back to the
  // summary so the poster renders immediately while detail loads.
  const seasonData = (seasonDetail && seasonDetail.id === seasonKey) ? seasonDetail : summary;
  const st = useMemo(() => (seasonData ? seasonStats(seasonData, TODAY) : null), [seasonData]);

  const loading = profileLoading && !profile;
  const error = profileError
    ? (profileError.response?.status === 404 ? 'Profil nenalezen' : 'Nepodařilo se načíst profil')
    : null;

  // All hooks must run on every render, so these stay ABOVE the early returns
  // below and tolerate a null `st`. (Calling them only after the loading guard
  // changes the hook count between renders and crashes React with
  // "Rendered more hooks than during the previous render.")
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
      const cat = e.category?.name || 'Akce';
      if (!buckets[cat]) buckets[cat] = { n: 0, p: 0 };
      buckets[cat].n += 1;
      buckets[cat].p += e.pts;
    });
    const sorted = Object.entries(buckets).sort((a, b) => b[1].p - a[1].p);
    const max = Math.max(...sorted.map(([, b]) => b.p), 1);
    return { sorted, max };
  }, [st]);

  const best = useMemo(() => (st ? st.evs.slice().sort((a, b) => b.pts - a.pts)[0] : undefined), [st]);

  // Bare /profil with no username → send to the logged-in user's own profile.
  if (!username) {
    if (authLoading) return <div className="profile-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítání…</div></div>;
    return <Navigate to={user ? `/profil/${user.username}` : '/prihlasit'} replace />;
  }
  if (loading) return <div className="profile-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítání profilu…</div></div>;
  if (error) return <div className="profile-page"><div style={{ padding: '2rem', textAlign: 'center', color: '#e15463' }}>Chyba: {error}</div></div>;
  // `st` is always set once `profile` exists (synthesized when seasonless), so
  // the page renders from profile-level data even for players with no points.
  if (!profile || !st) return <div className="profile-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Profil nenalezen</div></div>;

  const avg = st.evs.length ? Math.round(st.totalPts / st.evs.length) : 0;
  const allTotal = profile.total_points || 0;
  const initials = profile.full_name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || 'GO';

  const handleShare = () => shareLink(`${profile.full_name} — Game of Life`);

  const seasonTabs = profile.seasons?.map((s) => ({ key: s.id, label: s.label })) || [];
  const viewTabs = [
    { key: 'about', label: 'O mně' },
    { key: 'events', label: 'Akce', badge: st.evs.length },
    { key: 'points', label: 'Body', badge: st.totalPts },
  ];

  return (
    <div className="profile-page">
      <section className="poster">
        <div className="poster-img" />
        <div className="poster-grain" />
        <div className="poster-vignette" />

        <div className="poster-top">
          <div className="badges">
            {st.rank && <span className="ev-pill live">★ #{st.rank} Leaderboard</span>}
            <span className="ev-pill">Sezóna {st.label}</span>
          </div>
          <div className="poster-avatar">
            {profile.photo ? <img src={profile.photo} alt={profile.full_name} /> : initials}
          </div>
          <h1 className="poster-name">{profile.full_name}</h1>
          <div className="poster-handle">@{profile.username} · hraje od {profile.since}</div>
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
            {view === 'about' && (
              <>
                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 01 · O mně —</span><span className="meta">profil &amp; minulost</span></div>
                  <h2 className="sec-heading">Hraj naplno, <span className="pink">nebo vůbec.</span></h2>
                  <p className="about-quote">{profile.bio || 'Bez popisu profilu.'}</p>
                  <div className="about-meta">
                    {profile.city && <><span>{profile.city}</span><span className="dot" /></>}
                    {profile.favourite_categories?.length > 0 && <><span>{profile.favourite_categories.map((c) => c.name).join(' · ')}</span><span className="dot" /></>}
                    <span>Připojil se {profile.since}</span>
                  </div>

                  <div className="factgrid">
                    {profile.city && <div className="fact"><div className="l">Domácí město</div><div className="v">{profile.city.split(',')[0]}</div><div className="s">Kde se nejvíc pohybuje</div></div>}
                    <div className="fact"><div className="l">Hraje od</div><div className="v">{profile.since}</div><div className="s">{profile.seasons?.length || 0} sezóny</div></div>
                    <div className="fact"><div className="l">Celkem bodů</div><div className="v">{allTotal}</div><div className="s">napříč všemi sezónami</div></div>
                  </div>

                  {(profile.instagram || profile.strava || profile.spotify || profile.tiktok) && (
                    <div className="socials">
                      <div className="socials-label">— Najdeš ho na —</div>
                      <div className="socials-grid">
                        {profile.instagram && (
                          <a className="social" href={`https://instagram.com/${profile.instagram}`} target="_blank" rel="noopener noreferrer">
                            <span className="ico">IG</span>
                            <span className="lbl"><span className="p">Instagram</span><span className="h">@{profile.instagram}</span></span>
                            <span className="arr">↗</span>
                          </a>
                        )}
                        {profile.strava && (
                          <a className="social" href={`https://strava.com/athletes/${profile.strava}`} target="_blank" rel="noopener noreferrer">
                            <span className="ico">ST</span>
                            <span className="lbl"><span className="p">Strava</span><span className="h">{profile.strava}</span></span>
                            <span className="arr">↗</span>
                          </a>
                        )}
                        {profile.spotify && (
                          <a className="social" href={`https://spotify.com/user/${profile.spotify}`} target="_blank" rel="noopener noreferrer">
                            <span className="ico">SP</span>
                            <span className="lbl"><span className="p">Spotify</span><span className="h">{profile.spotify}</span></span>
                            <span className="arr">↗</span>
                          </a>
                        )}
                        {profile.tiktok && (
                          <a className="social" href={`https://tiktok.com/@${profile.tiktok}`} target="_blank" rel="noopener noreferrer">
                            <span className="ico">TT</span>
                            <span className="lbl"><span className="p">TikTok</span><span className="h">@{profile.tiktok}</span></span>
                            <span className="arr">↗</span>
                          </a>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}

            {view === 'events' && (
              <>
                {upcoming.length > 0 && (
                  <div className="section">
                    <div className="sec-rule" />
                    <div className="sec-eyebrow"><span>— 03 · Nadcházející —</span><span className="meta">+{st.futurePts} pts na cestě</span></div>
                    <h2 className="sec-heading">Co ho <span className="pink">čeká.</span></h2>
                    <StatList
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
                  <div className="sec-eyebrow"><span>— 04 · Absolvované —</span><span className="meta">+{st.pastPts} pts zatím</span></div>
                  <h2 className="sec-heading">Co má <span className="pink">za sebou.</span></h2>
                  <StatList
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
                  <div className="sec-eyebrow"><span>— 05 · Body v čase —</span><span className="meta">křivka sezóny</span></div>
                  <h2 className="sec-heading">Křivka <span className="pink">sezóny.</span></h2>

                  <div className="chart-card">
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
                    <div className="mini-stats">
                      <div className="mini"><div className="l">Absolvováno</div><div className="v pink">{st.pastPts}</div><div className="s">bodů zatím</div></div>
                      <div className="mini"><div className="l">Nadcházející</div><div className="v">{st.futurePts}</div><div className="s">bodů na cestě</div></div>
                      <div className="mini"><div className="l">Nejlepší akce</div><div className="v yellow">{best ? `+${best.pts}` : '—'}</div><div className="s">{best ? best.name : 'zatím nic'}</div></div>
                      <div className="mini"><div className="l">Průměr / akce</div><div className="v">{avg}</div><div className="s">bodů</div></div>
                    </div>
                  </div>
                </div>

                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 06 · Kategorie —</span><span className="meta">{cats.sorted.length} kategorií</span></div>
                  <h2 className="sec-heading">V čem <span className="pink">jede.</span></h2>
                  <div className="cat-list">
                    {cats.sorted.length
                      ? cats.sorted.map(([cat, b]) => (
                        <div className="cat-row" key={cat}>
                          <span className="name">{cat}</span>
                          <span className="bar"><i style={{ width: `${Math.round((b.p / cats.max) * 100)}%` }} /></span>
                          <span className="meta">{b.n}× · <b>+{b.p}</b></span>
                        </div>
                      ))
                      : <div className="empty">Žádná data v této sezóně.</div>}
                  </div>
                </div>
              </>
            )}
          </section>
        </main>
      </div>

      <div className="back-strip">
        <div className="back-strip-inner">
          <Link className="back-link" to="/">← Zpět na hlavní stránku</Link>
          <div className="back-actions">
            {profile?.is_own_profile && <Button as="link" to="/upravit-profil" variant="action">✎ Upravit profil</Button>}
            <Button variant="ghost" onClick={handleShare}>Sdílet profil</Button>
            {profile?.is_own_profile && <Button variant="ghost" onClick={() => navigate('/')}>Odhlásit se</Button>}
          </div>
        </div>
      </div>
    </div>
  );
}

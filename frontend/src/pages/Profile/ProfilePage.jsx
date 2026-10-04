import { useMemo, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import PillTabs from '../../components/PillTabs/PillTabs';
import Button from '../../components/Button/Button';
import Badge from '../../components/Badge/Badge';
import PageState from '../../components/PageState/PageState';
import SectionHeader from '../../components/SectionHeader/SectionHeader';
import { TicketFrame } from '../../components/DashedBorder/DashedBorder';
import { useSeasonView } from './useSeasonView';
import { ProfileCredits, EventsSections, PointsSections } from './profileSections';
import { fetchProfile, fetchProfileSeason } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { queryKeys } from '../../services/queryKeys';
import { useAuth } from '../../context/AuthContext';
import { CACHE_TTL } from '../../constants/config';
import { shareLink } from '../../utils/shareUrl';
import { initials } from '../../utils/name';
import '../../styles/poster-hero.css';
import './ProfilePage.css';
import { plural } from '../../utils/plural';
import { SOCIALS, socialHref, socialLabel } from './socials';

const TODAY = new Date();

const badgeWord = (n) => plural(n, 'odznak', 'odznaky', 'odznaků');

export default function ProfilePage() {
  const { username } = useParams();
  const navigate = useNavigate();
  const { user, loading: authLoading, logout } = useAuth();
  const [pickedSeason, setPickedSeason] = useState(null); // user's explicit pick (season id)
  const [view, setView] = useState('about');

  // Core profile (stats, rank, upcoming RSVPs, season summaries — no events).
  const { data: profile, loading: profileLoading, error: profileError } = useCachedQuery(
    queryKeys.profile(username),
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
    queryKeys.profile(username, seasonKey),
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
  // Shared derivation (stats + sorted event lists + category breakdown). Runs
  // unconditionally and tolerates a null seasonData, so it stays above the
  // early returns and keeps the hook count stable across renders.
  const { st, upcoming, past, cats } = useSeasonView(seasonData, TODAY);

  const loading = profileLoading && !profile;
  const error = profileError
    ? (profileError.response?.status === 404 ? 'Profil nenalezen' : 'Nepodařilo se načíst profil')
    : null;

  // Bare /profil with no username → send to the logged-in user's own profile.
  if (!username) {
    if (authLoading) return <div className="profile-page"><PageState kind="loading" fill text="Načítám…" /></div>;
    return <Navigate to={user ? `/profil/${user.username}` : '/prihlasit'} replace />;
  }
  if (loading) return <div className="profile-page"><PageState kind="loading" fill text="Načítám profil…" /></div>;
  if (error) return <div className="profile-page"><PageState kind="error" fill text={`Profil se nepodařilo načíst: ${error}`} /></div>;
  // `st` is always set once `profile` exists (synthesized when seasonless), so
  // the page renders from profile-level data even for players with no points.
  if (!profile || !st) return <div className="profile-page"><PageState kind="empty" fill text="Profil nenalezen." /></div>;

  const avatarInitials = initials(profile.full_name, 'GO');
  const linkedSocials = SOCIALS.filter((sc) => profile[sc.key]);

  const handleShare = () => shareLink(`${profile.full_name} — Game of Life`);
  // Actually log out (the label promises it), then land on the homepage.
  const handleLogout = async () => { await logout(); navigate('/'); };

  const seasonTabs = profile.seasons?.map((s) => ({ key: s.id, label: s.label })) || [];
  // Sections the owner withheld are absent from the payload, so their tabs would
  // read "Akce 0" / "Body 0" — drop them rather than display a number that isn't
  // the truth.
  const hidden = profile.hidden || [];
  const viewTabs = [
    { key: 'about', label: 'O mně' },
    !hidden.includes('events') && { key: 'events', label: 'Akce', badge: st.evs.length },
    !hidden.includes('points') && { key: 'points', label: 'Body', badge: st.totalPts },
  ].filter(Boolean);

  return (
    <div className="profile-page">
      <section className="poster">
        <div className="poster-img" />
        <div className="poster-grain" />
        <div className="poster-vignette" />

        <div className="poster-top">
          <div className="badges">
            {st.rank && <Badge tone="live">★ #{st.rank} Leaderboard</Badge>}
            <Badge>Sezóna {st.label}</Badge>
          </div>
          <div className="poster-avatar">
            {profile.photo ? <img src={profile.photo} alt={profile.full_name} /> : avatarInitials}
          </div>
          <h1 className="poster-name">{profile.full_name}</h1>
          <div className="poster-handle">{profile.username ? `@${profile.username} · ` : ''}hraje od {profile.since}</div>
        </div>

        <ProfileCredits st={st} hidden={hidden} />
      </section>

      <div className="action-bar">
        <div className="action-inner">
          <PillTabs tabs={seasonTabs} active={seasonKey} onChange={setPickedSeason} />
          <PillTabs tabs={viewTabs} active={view} onChange={setView} />
        </div>
      </div>

      <div className="poster-body">
        <main className="profile-main">
          <section className="profile-view" key={view}>
            {view === 'about' && (
              <>
                <div className="section">
                  <SectionHeader eyebrow="01 · O mně" meta="profil & minulost" heading={<>Joy<span className="pink">Maxxer</span></>} />
                  <p className="gol-quote">{profile.bio || 'Bez popisu profilu.'}</p>
                  {(profile.city || profile.favourite_categories?.length > 0) && (
                    <div className="about-meta">
                      {profile.city && <span>{profile.city}</span>}
                      {profile.city && profile.favourite_categories?.length > 0 && <span className="dot" />}
                      {profile.favourite_categories?.length > 0 && <span>{profile.favourite_categories.map((c) => c.name).join(' · ')}</span>}
                    </div>
                  )}

                  {profile.city && (
                    <div className="factgrid">
                      <div className="fact"><TicketFrame /><div className="fact-in"><div className="l">Domácí město</div><div className="v">{profile.city.split(',')[0]}</div><div className="s">Kde se nejvíc pohybuje</div></div></div>
                    </div>
                  )}

                  {/* Answered profile questions. The payload omits unanswered
                      ones, so there is nothing to filter here — and nothing to
                      render at all for someone who skipped them. */}
                  {profile.answers?.length > 0 && (
                    <div className="qa">
                      <div className="qa-label">Pár otázek</div>
                      <dl className="qa-list">
                        {profile.answers.map((a) => (
                          <div className="qa-item" key={a.question_id}>
                            <dt className="qa-q">{a.question}</dt>
                            <dd className="qa-a">{a.answer}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  )}

                  {linkedSocials.length > 0 && (
                    <div className="socials">
                      <div className="socials-label">Najdeš na</div>
                      <div className="socials-grid">
                        {linkedSocials.map((sc) => (
                          <a key={sc.key} className="social" href={socialHref(sc, profile[sc.key])} target="_blank" rel="noopener noreferrer">
                            <TicketFrame />
                            <span className="social-in">
                              <span className="ico">{sc.ico}</span>
                              <span className="lbl"><span className="p">{sc.label}</span><span className="h">{socialLabel(sc, profile[sc.key])}</span></span>
                              <span className="arr">↗</span>
                            </span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {profile.badges?.length > 0 && (
                  <div className="section">
                    <SectionHeader eyebrow="Sbírka" meta={`${profile.badges.length} ${badgeWord(profile.badges.length)}`} heading={<>Od<span className="pink">znaky</span></>} />
                    <div className="badge-grid">
                      {profile.badges.map((b) => (
                        <div className="badge-item" key={b.id} title={b.description || b.name}>
                          <TicketFrame />
                          <div className="badge-in">
                            {b.image
                              ? <img className="badge-img" src={b.image} alt={b.name} loading="lazy" />
                              : <span className="badge-fallback">{b.name.slice(0, 2).toUpperCase()}</span>}
                            <span className="badge-name">{b.name}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {view === 'events' && (
              <EventsSections st={st} upcoming={upcoming} past={past} startNum={2} />
            )}

            {view === 'points' && (
              <PointsSections st={st} cats={cats} today={TODAY} startNum={4} />
            )}
          </section>
        </main>
      </div>

      <div className="back-strip">
        <div className="back-strip-inner">
          {/* Navigation = 3D buttons (frost for "back"); round pills = in-place actions. */}
          <Button as="link" to="/" variant="frost" className="back-home">← Zpět na hlavní stránku</Button>
          <div className="back-actions">
            {profile?.is_own_profile && <Button as="link" to="/upravit-profil">✎ Upravit profil</Button>}
            <Button variant="ghost" onClick={handleShare}>Sdílet profil</Button>
            {profile?.is_own_profile && <Button variant="ghost" onClick={handleLogout}>Odhlásit se</Button>}
          </div>
        </div>
      </div>
    </div>
  );
}

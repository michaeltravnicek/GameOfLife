import { useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { fetchProfile } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import { useAuth } from '../../context/AuthContext';
import Button from '../../components/Button/Button';
import TabBar from '../../components/TabBar/TabBar';
import SectionHeader from '../../components/SectionHeader/SectionHeader';
import './ProfilePage.css';

const MONTHS_SHORT = ['Led','Úno','Bře','Dub','Kvě','Čvn','Čvc','Srp','Zář','Říj','Lis','Pro'];
const fmt = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getDate()}. ${MONTHS_SHORT[d.getMonth()]}`;
};

export default function ProfilePage() {
  const { username } = useParams();
  const { user, logout, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('upcoming');

  const { data: profile, error: queryError } = useCachedQuery(
    `profile:${username}`,
    () => fetchProfile(username),
    { enabled: !!username, ttl: CACHE_TTL.PROFILE },
  );
  const error = queryError
    ? (queryError.response?.status === 404 ? 'Profil nenalezen.' : 'Chyba při načítání profilu.')
    : '';

  if (!username) {
    if (authLoading) return null;
    if (!user) return <Navigate to="/prihlasit" replace />;
    return <Navigate to={`/profil/${user.username}`} replace />;
  }

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const handleShare = () => {
    const url = window.location.href;
    if (navigator.share) {
      // Web Share AbortError when user dismisses the share sheet → ignore.
      navigator.share({ title: document.title, url }).catch(() => {});
    } else {
      navigator.clipboard?.writeText(url);
    }
  };

  if (error) {
    return (
      <div className="profile-page">
        <p style={{ textAlign: 'center', padding: '120px 20px', color: '#fff' }}>{error}</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="profile-page">
        <p style={{ textAlign: 'center', padding: '120px 20px', color: '#fff' }}>Načítám profil…</p>
      </div>
    );
  }

  const displayName = profile.full_name || profile.username;

  return (
    <div className="profile-page">
      <div className="stage" />
      <div className="grain" />

      <header className="hero">
        <div className="eyebrow">Profil hráče · Sezóna 2025/26</div>

        <div className="podium-stack">
          <div className="trophy">🏆</div>
          <div className="podium-bars">
            <div className="bar gold"><div className="bar-num">1.</div></div>
            <div className="bar silver"><div className="bar-num">2.</div></div>
            <div className="bar bronze"><div className="bar-num">3.</div></div>
          </div>
        </div>

        <h1>{displayName}</h1>
        <div className="handle">@{profile.username}</div>
        <p className="tagline">Hráč Game of Life. Prohlédni si jeho absolvované akce.</p>

        <div className="stats-inline">
          <span><span className="val">{profile.rank ? `${profile.rank}.` : '—'}</span> v pořadí</span>
          <span>/</span>
          <span><span className="val">{profile.total_points}</span> bodů</span>
          <span>/</span>
          <span><span className="val">{profile.total_events}</span> akcí</span>
        </div>

        <div className="divider" />
      </header>

      <div className="actions">
        {profile.is_own_profile ? (
          <>
            <Button variant="ghost" size="sm" onClick={handleShare}>Sdílet profil</Button>
            <Button variant="ghost" size="sm" onClick={handleLogout}>Odhlásit se</Button>
          </>
        ) : (
          <Button variant="ghost" size="sm" onClick={handleShare}>Sdílet profil</Button>
        )}
      </div>

      <main className="profile-main">
        <section className="section">
          <SectionHeader eyebrow="— 01 · O hráči —" heading={`${displayName}, vlastními slovy.`} />
          <div className="about-card">
            <p className="about-empty">Tento hráč zatím o sobě nic nenapsal.</p>
          </div>
        </section>

        <section className="section">
          <SectionHeader eyebrow="— 02 · Činnost —" heading="Co hraje a co odehrál." />

          <div className="tab-row">
            <TabBar
              tabs={[{key:'upcoming',label:'Nadcházející'},{key:'past',label:'Absolvované'}]}
              active={activeTab}
              onChange={setActiveTab}
            />
          </div>

          {activeTab === 'upcoming' && (
            <div className="events-grid">
              {profile.upcoming_rsvps?.length ? profile.upcoming_rsvps.map((ev) => (
                <Link key={ev.slug} className="ev-card" to={`/akce/${ev.slug}`}>
                  <img className="ev-badge" src={ev.logo || '/logos/GOL_main_logo_pink.png'} alt={ev.name} />
                  <span className="ev-tag">Event</span>
                  <div className="ev-name">{ev.name}</div>
                  <div className="ev-meta">
                    <div className="ev-row">📅 {fmt(ev.date)}</div>
                    <div className="ev-row">📍 {ev.place}</div>
                    <div className="ev-row">🏆 +{ev.points} pts</div>
                  </div>
                </Link>
              )) : <div className="empty-msg">Žádné nadcházející akce.</div>}
            </div>
          )}

          {activeTab === 'past' && (
            <div className="list">
              {profile.past_events?.length ? profile.past_events.map((ev) => (
                <Link key={ev.slug} to={`/akce/${ev.slug}`} className="row" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <span className="ev-cat">Event</span>
                  <div className="ev-info">
                    <div className="nm">{ev.name}</div>
                    <div className="loc">📍 {ev.place}</div>
                  </div>
                  <div className="ev-date">{fmt(ev.date)}</div>
                  <div className="ev-pts">+{ev.points}<span className="u">pts</span></div>
                </Link>
              )) : <div className="empty">Žádné absolvované akce.</div>}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

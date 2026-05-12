import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { fetchProfile } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
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
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('upcoming');

  useEffect(() => {
    if (!username) return;
    setError('');
    setProfile(null);
    fetchProfile(username)
      .then(setProfile)
      .catch((e) => {
        setError(e.response?.status === 404 ? 'Profil nenalezen.' : 'Chyba při načítání profilu.');
      });
  }, [username]);

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
    if (navigator.share) navigator.share({ title: document.title, url: location.href });
    else navigator.clipboard.writeText(location.href);
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
            <button className="btn-pill ghost" type="button" onClick={handleShare}>Sdílet profil</button>
            <button className="btn-pill ghost" type="button" onClick={handleLogout}>Odhlásit se</button>
          </>
        ) : (
          <button className="btn-pill ghost" type="button" onClick={handleShare}>Sdílet profil</button>
        )}
      </div>

      <main className="profile-main">
        <section className="section">
          <div className="sec-rule" />
          <div className="sec-eyebrow">— 01 · O hráči —</div>
          <h2 className="sec-heading">{displayName}, vlastními slovy.</h2>
          <div className="about-card">
            <p className="about-empty">Tento hráč zatím o sobě nic nenapsal.</p>
          </div>
        </section>

        <section className="section">
          <div className="sec-rule" />
          <div className="sec-eyebrow">— 02 · Činnost —</div>
          <h2 className="sec-heading">Co hraje a co odehrál.</h2>

          <div className="tab-row">
            <div className="pill-group">
              <button
                className={`pill${activeTab === 'upcoming' ? ' on-pink' : ''}`}
                onClick={() => setActiveTab('upcoming')}
              >Nadcházející</button>
              <button
                className={`pill${activeTab === 'past' ? ' on-pink' : ''}`}
                onClick={() => setActiveTab('past')}
              >Absolvované</button>
            </div>
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

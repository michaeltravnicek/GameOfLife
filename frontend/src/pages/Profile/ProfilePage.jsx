import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { fetchProfile } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import './ProfilePage.css';

const MONTHS = ['ledna', 'února', 'března', 'dubna', 'května', 'června', 'července', 'srpna', 'září', 'října', 'listopadu', 'prosince'];
const fmt = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getDate()}. ${MONTHS[d.getMonth()]}`;
};
const initials = (n) =>
  (n || '').split(' ').map((w) => w[0]).filter(Boolean).join('').slice(0, 2).toUpperCase();

export default function ProfilePage() {
  const { username } = useParams();
  const { user, logout, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');

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

  // /profil with no username → redirect to own profile or login
  if (!username) {
    if (authLoading) return null;
    if (!user) return <Navigate to="/prihlasit" replace />;
    return <Navigate to={`/profil/${user.username}`} replace />;
  }

  const handleLogout = async () => {
    await logout();
    navigate('/');
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
      <section className="hero">
        <div className="hero-bg" />
        <div className="hero-overlay" />
        {profile.rank && (
          <div className="rank-badge">
            <span className="rn">🏆</span>
            <span className="rl">{profile.rank}. místo</span>
          </div>
        )}
        <div className="hero-inner">
          <div className="avatar">
            {profile.photo ? <img src={profile.photo} alt={displayName} /> : initials(displayName)}
          </div>
          <div className="hero-text">
            <div className="eyebrow">Profil hráče · 2025/26</div>
            <div className="hero-name">{displayName}</div>
            <div className="hero-handle">@{profile.username} · Sezóna 2025/26</div>
          </div>
        </div>
      </section>

      <section className="stats-section">
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-num gold">{profile.rank ? `${profile.rank}.` : '—'}</div>
            <div className="stat-label">Pořadí</div>
          </div>
          <div className="stat-card">
            <div className="stat-num">{profile.total_points}</div>
            <div className="stat-label">Bodů celkem</div>
          </div>
          <div className="stat-card">
            <div className="stat-num">{profile.total_events}</div>
            <div className="stat-label">Akcí v sezóně</div>
          </div>
        </div>
      </section>

      <section className="events-section">
        <h2 className="sec-title"><span className="star">✦</span> Nadcházející akce <span className="star">✦</span></h2>
        <div className="events-grid">
          {profile.upcoming_rsvps.length ? profile.upcoming_rsvps.map((ev) => (
            <Link key={ev.slug} className="ev-card" to={`/akce/${ev.slug}`}>
              <div className="ev-name">{ev.name}</div>
              <div className="ev-meta">
                <div className="ev-row">📅 {fmt(ev.date)}</div>
                <div className="ev-row">📍 {ev.place}</div>
                <div className="ev-row">🏆 +{ev.points} pts</div>
              </div>
            </Link>
          )) : (
            <p style={{ color: 'rgba(255,241,212,.5)', fontStyle: 'italic', textAlign: 'center', padding: '40px 0', gridColumn: '1/-1' }}>
              Žádné nadcházející akce.
            </p>
          )}
        </div>
        <div className="see-all">
          <Link to="/akce" className="btn-pill">Všechny akce <span className="arr"></span></Link>
        </div>
      </section>

      {profile.is_own_profile && (
        <section className="about-section">
          <div className="about-inner">
            <div>
              <div className="about-eyebrow">— O mně —</div>
              <h3 className="about-heading">Tvoje cesta začíná tady.</h3>
              <p className="about-body">Sleduj nadcházející akce, sbírej body a stoupej v žebříčku.</p>
              <div className="btn-row">
                <Link to="/akce" className="btn-pill">Najít akci <span className="arr"></span></Link>
                <Link to="/leaderboard" className="btn-pill ghost">Leaderboard</Link>
              </div>
            </div>
            <div className="actions-col">
              <button className="btn-action ghost" onClick={handleLogout}>Odhlásit se</button>
            </div>
          </div>
        </section>
      )}

      <section className="past-section">
        <div className="past-inner">
          <div className="group-label">Absolvované akce · <span>{profile.past_events.length}</span> akcí</div>
          <div className="list">
            <div className="list-inner">
              {profile.past_events.length ? profile.past_events.map((ev) => (
                <Link key={ev.slug} to={`/akce/${ev.slug}`} className="row" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div className="ev-info">
                    <div className="nm">{ev.name}</div>
                    <div className="loc">📍 {ev.place}</div>
                  </div>
                  <div className="ev-date">{fmt(ev.date)}</div>
                  <div className="ev-pts">+{ev.points}<span className="u">pts</span></div>
                </Link>
              )) : <div className="empty">Zatím žádné absolvované akce.</div>}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

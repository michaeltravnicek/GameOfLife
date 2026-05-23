import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { fetchProfile } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import Avatar from '../../components/Avatar/Avatar';
import Button from '../../components/Button/Button';
import './ProfilePageV3.css';

const MONTHS_SHORT = ['Led','Úno','Bře','Dub','Kvě','Čvn','Čvc','Srp','Zář','Říj','Lis','Pro'];
const fmt = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getDate()}. ${MONTHS_SHORT[d.getMonth()]}`;
};

/* ── Animated count-up for stat numbers ───────────────────── */
function useCountUp(target, duration = 1100) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (target == null || isNaN(target)) { setN(0); return; }
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setN(target);
      return;
    }
    let raf, start;
    const step = (t) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(eased * target));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return n;
}

/* ── Achievement catalogue (purely cosmetic, derived from profile data) ── */
function getAchievements(profile) {
  const total = profile?.total_events || 0;
  const points = profile?.total_points || 0;
  const rank = profile?.rank;
  return [
    { key: 'first',   icon: '🎯', label: 'První akce',     unlocked: total >= 1,   hint: 'Účast na první akci' },
    { key: 'streak',  icon: '🔥', label: 'Hot streak',     unlocked: total >= 3,   hint: '3+ akce za sebou' },
    { key: 'climber', icon: '⛰',  label: 'Climber',        unlocked: total >= 5,   hint: '5+ absolvovaných akcí' },
    { key: 'century', icon: '💯', label: 'Stovka',         unlocked: points >= 100, hint: '100+ bodů celkem' },
    { key: 'top10',   icon: '🏅', label: 'Top 10',         unlocked: rank != null && rank <= 10, hint: 'Pozice 1.–10. v žebříčku' },
    { key: 'podium',  icon: '🏆', label: 'Na bedně',       unlocked: rank != null && rank <= 3,  hint: 'Pozice 1.–3. v žebříčku' },
    { key: 'legend',  icon: '⭐', label: 'Legenda',        unlocked: points >= 500, hint: '500+ bodů celkem' },
    { key: 'social',  icon: '🤝', label: 'Komunitní',      unlocked: total >= 10,  hint: '10+ akcí' },
  ];
}

/* ── Confetti burst spawner ───────────────────────────────── */
function spawnConfetti(el) {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
  const colors = ['#e15463', '#f5c842', '#fff1d4', '#2d2a8e', '#a8e6cf'];
  for (let i = 0; i < 28; i++) {
    const piece = document.createElement('span');
    piece.className = 'pv3-confetti';
    piece.style.background = colors[i % colors.length];
    piece.style.setProperty('--dx', `${(Math.random() - 0.5) * 280}px`);
    piece.style.setProperty('--dy', `${-120 - Math.random() * 200}px`);
    piece.style.setProperty('--rot', `${Math.random() * 720 - 360}deg`);
    piece.style.setProperty('--delay', `${Math.random() * 80}ms`);
    el.appendChild(piece);
    setTimeout(() => piece.remove(), 1400);
  }
}

export default function ProfilePageV3() {
  const { username } = useParams();
  const { user, logout, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('upcoming');
  const cardRef = useRef(null);
  const stageRef = useRef(null);

  /* Fetch profile */
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

  /* 3D tilt on hero card + parallax on background orbs */
  useEffect(() => {
    const card = cardRef.current;
    const stage = stageRef.current;
    if (!card) return;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    if (window.matchMedia?.('(hover: none)').matches) return; // skip on touch

    let raf;
    const onMove = (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = card.getBoundingClientRect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const dx = (e.clientX - cx) / r.width;
        const dy = (e.clientY - cy) / r.height;
        const tiltX = Math.max(-1, Math.min(1, -dy)) * 6;
        const tiltY = Math.max(-1, Math.min(1, dx)) * 6;
        card.style.setProperty('--rx', `${tiltX}deg`);
        card.style.setProperty('--ry', `${tiltY}deg`);
        card.style.setProperty('--mx', `${(dx + 0.5) * 100}%`);
        card.style.setProperty('--my', `${(dy + 0.5) * 100}%`);
        if (stage) {
          stage.style.setProperty('--orb-x', `${dx * 30}px`);
          stage.style.setProperty('--orb-y', `${dy * 30}px`);
        }
      });
    };
    const onLeave = () => {
      card.style.setProperty('--rx', '0deg');
      card.style.setProperty('--ry', '0deg');
    };
    window.addEventListener('mousemove', onMove);
    card.addEventListener('mouseleave', onLeave);
    return () => {
      window.removeEventListener('mousemove', onMove);
      card.removeEventListener('mouseleave', onLeave);
      cancelAnimationFrame(raf);
    };
  }, [profile]);

  if (!username) {
    if (authLoading) return null;
    if (!user) return <Navigate to="/prihlasit" replace />;
    return <Navigate to={`/profil-v3/${user.username}`} replace />;
  }

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const handleShare = () => {
    if (navigator.share) {
      // Web Share AbortError when user dismisses the share sheet → ignore.
      navigator.share({ title: document.title, url: window.location.href }).catch(() => {});
    } else {
      navigator.clipboard?.writeText(window.location.href);
    }
  };

  const handleAvatarClick = (e) => {
    const burst = e.currentTarget.querySelector('.pv3-confetti-stage');
    if (burst) spawnConfetti(burst);
  };

  if (error) {
    return (
      <div className="pv3-page">
        <div className="pv3-bg" />
        <div className="pv3-grain" />
        <p className="pv3-status">{error}</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="pv3-page">
        <div className="pv3-bg" />
        <div className="pv3-grain" />
        <div className="pv3-loader" aria-label="Načítám">
          <span /><span /><span />
        </div>
      </div>
    );
  }

  const displayName = profile.full_name || profile.username;
  const achievements = getAchievements(profile);
  const unlockedCount = achievements.filter(a => a.unlocked).length;

  /* XP progress: cosmetic — fills based on points within current "level" of 100 */
  const levelSize = 100;
  const level = Math.floor((profile.total_points || 0) / levelSize) + 1;
  const xpInLevel = (profile.total_points || 0) % levelSize;
  const xpPercent = Math.min(100, (xpInLevel / levelSize) * 100);

  return (
    <div className="pv3-page">
      <div className="pv3-bg" ref={stageRef}>
        <div className="pv3-orb pv3-orb-1" />
        <div className="pv3-orb pv3-orb-2" />
        <div className="pv3-orb pv3-orb-3" />
      </div>
      <div className="pv3-grain" />
      <div className="pv3-scan" aria-hidden="true" />

      {/* ─────────────── HERO PLAYER CARD ─────────────── */}
      <header className="pv3-hero">
        <div className="pv3-marquee" aria-hidden="true">
          <div className="pv3-marquee-track">
            {Array.from({ length: 8 }).map((_, i) => (
              <span key={i}>SEASON 2025/26 ✦ PLAYER PROFILE ✦ </span>
            ))}
          </div>
        </div>

        <div className="pv3-card-wrap">
          <div
            ref={cardRef}
            className="pv3-card"
            style={{ '--rx': '0deg', '--ry': '0deg', '--mx': '50%', '--my': '50%' }}
          >
            <div className="pv3-card-shine" aria-hidden="true" />
            <div className="pv3-card-grid" aria-hidden="true" />

            <div className="pv3-card-head">
              <div className="pv3-card-meta">
                <span className="pv3-card-id">№ {String(profile.id || 0).padStart(4, '0')}</span>
                <span className="pv3-card-dot" />
                <span className="pv3-card-tag">PLAYER · LIVE</span>
              </div>
              <div className="pv3-card-level">
                <span className="pv3-level-label">LV.</span>
                <span className="pv3-level-num">{level}</span>
              </div>
            </div>

            <div className="pv3-avatar-row">
              <button
                type="button"
                className="pv3-avatar-btn"
                onClick={handleAvatarClick}
                aria-label="Confetti"
              >
                <span className="pv3-avatar-ring" />
                <span className="pv3-avatar-ring pv3-avatar-ring-2" />
                <span className="pv3-avatar-glow" />
                <Avatar
                  name={displayName}
                  photo={profile.photo}
                  size="xl"
                  className="pv3-avatar"
                />
                <span className="pv3-confetti-stage" aria-hidden="true" />
              </button>

              <div className="pv3-name-block">
                <div className="pv3-name-eyebrow">PLAYER</div>
                <h1 className="pv3-name">{displayName}</h1>
                <div className="pv3-handle">@{profile.username}</div>
              </div>
            </div>

            <div className="pv3-xp">
              <div className="pv3-xp-label">
                <span>XP do dalšího levelu</span>
                <span className="pv3-xp-num">{xpInLevel} / {levelSize}</span>
              </div>
              <div className="pv3-xp-track">
                <div
                  className="pv3-xp-fill"
                  style={{ width: `${xpPercent}%` }}
                >
                  <div className="pv3-xp-shine" />
                </div>
              </div>
            </div>

            <div className="pv3-stats">
              <Stat label="Rank"   value={profile.rank}         icon="◆" suffix="."  highlight />
              <Stat label="Body"   value={profile.total_points} icon="✦" suffix="pts" />
              <Stat label="Akcí"   value={profile.total_events} icon="⚑"             />
            </div>

            <div className="pv3-card-foot">
              <span>BUILD · 2025.{String(level).padStart(2, '0')}</span>
              <span>{unlockedCount}/{achievements.length} achievementů</span>
            </div>
          </div>
        </div>

        <div className="pv3-actions">
          {profile.is_own_profile ? (
            <>
              <Button variant="ghost" size="sm" onClick={handleShare}>↗ Sdílet profil</Button>
              <Button variant="ghost" size="sm" onClick={handleLogout}>Odhlásit se</Button>
            </>
          ) : (
            <Button variant="ghost" size="sm" onClick={handleShare}>↗ Sdílet profil</Button>
          )}
        </div>
      </header>

      {/* ─────────────── ACHIEVEMENTS ─────────────── */}
      <section className="pv3-section pv3-section-achv">
        <div className="pv3-sec-head">
          <span className="pv3-sec-eyebrow">— 01 · Achievementy —</span>
          <h2 className="pv3-sec-title">Co už zvládl</h2>
          <span className="pv3-sec-count">{unlockedCount} / {achievements.length}</span>
        </div>

        <div className="pv3-badges">
          {achievements.map((a, i) => (
            <button
              key={a.key}
              type="button"
              className={`pv3-badge${a.unlocked ? ' is-unlocked' : ' is-locked'}`}
              style={{ '--i': i }}
              aria-label={`${a.label}: ${a.hint}${a.unlocked ? '' : ' (zamčeno)'}`}
            >
              <span className="pv3-badge-icon">{a.unlocked ? a.icon : '🔒'}</span>
              <span className="pv3-badge-label">{a.label}</span>
              <span className="pv3-badge-hint">{a.hint}</span>
            </button>
          ))}
        </div>
      </section>

      {/* ─────────────── ABOUT ─────────────── */}
      <section className="pv3-section">
        <div className="pv3-sec-head">
          <span className="pv3-sec-eyebrow">— 02 · O hráči —</span>
          <h2 className="pv3-sec-title">{displayName}, vlastními slovy</h2>
        </div>
        <div className="pv3-about-card">
          <div className="pv3-quote-mark">"</div>
          <p className="pv3-about-text">
            {profile.bio || 'Tento hráč zatím o sobě nic nenapsal. Možná je dnes na akci a nemá čas — což je vlastně to nejlepší vysvětlení.'}
          </p>
          <div className="pv3-quote-mark pv3-quote-mark-end">"</div>
        </div>
      </section>

      {/* ─────────────── ACTIVITY ─────────────── */}
      <section className="pv3-section">
        <div className="pv3-sec-head">
          <span className="pv3-sec-eyebrow">— 03 · Činnost —</span>
          <h2 className="pv3-sec-title">Co hraje a co odehrál</h2>
        </div>

        <div className="pv3-tabs" role="tablist">
          {[
            { key: 'upcoming', label: 'Nadcházející', count: profile.upcoming_rsvps?.length ?? 0 },
            { key: 'past',     label: 'Absolvované', count: profile.past_events?.length ?? 0 },
          ].map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={activeTab === t.key}
              className={`pv3-tab${activeTab === t.key ? ' is-active' : ''}`}
              onClick={() => setActiveTab(t.key)}
            >
              <span>{t.label}</span>
              <span className="pv3-tab-count">{t.count}</span>
            </button>
          ))}
        </div>

        {activeTab === 'upcoming' && (
          <div className="pv3-events-grid">
            {profile.upcoming_rsvps?.length ? profile.upcoming_rsvps.map((ev, i) => (
              <Link
                key={ev.slug}
                className="pv3-event"
                to={`/akce/${ev.slug}`}
                style={{ '--i': i, '--tilt': `${(i % 2 === 0 ? -1 : 1) * 1.5}deg` }}
              >
                <div className="pv3-event-bg" />
                <img
                  className="pv3-event-badge"
                  src={ev.logo || '/logos/GOL_main_logo_pink.png'}
                  alt=""
                  loading="lazy"
                />
                <div className="pv3-event-corner" aria-hidden="true" />
                <div className="pv3-event-tag">UPCOMING</div>
                <div className="pv3-event-name">{ev.name}</div>
                <div className="pv3-event-meta">
                  <span><span className="pv3-event-ic">⌖</span> {fmt(ev.date)}</span>
                  <span><span className="pv3-event-ic">◉</span> {ev.place}</span>
                </div>
                <div className="pv3-event-foot">
                  <span className="pv3-event-pts">+{ev.points}<small>pts</small></span>
                  <span className="pv3-event-go">Vstoupit →</span>
                </div>
              </Link>
            )) : (
              <EmptyState
                icon="◇"
                title="Žádné nadcházející akce"
                hint="Mrkni do kalendáře a přidej se k další výzvě."
                ctaTo="/akce"
                ctaLabel="Prozkoumat akce →"
              />
            )}
          </div>
        )}

        {activeTab === 'past' && (
          <div className="pv3-log">
            {profile.past_events?.length ? profile.past_events.map((ev, i) => (
              <Link
                key={ev.slug}
                to={`/akce/${ev.slug}`}
                className="pv3-log-row"
                style={{ '--i': i }}
              >
                <span className="pv3-log-num">{String(i + 1).padStart(2, '0')}</span>
                <span className="pv3-log-bullet" />
                <span className="pv3-log-info">
                  <span className="pv3-log-name">{ev.name}</span>
                  <span className="pv3-log-place">◉ {ev.place}</span>
                </span>
                <span className="pv3-log-date">{fmt(ev.date)}</span>
                <span className="pv3-log-pts">
                  <span className="pv3-log-plus">+</span>
                  {ev.points}
                  <small>pts</small>
                </span>
                <span className="pv3-log-arrow">→</span>
              </Link>
            )) : (
              <EmptyState
                icon="○"
                title="Žádné absolvované akce"
                hint="Až se zúčastníš první akce, objeví se tady."
              />
            )}
          </div>
        )}
      </section>

      {/* ─────────────── BACK STRIP ─────────────── */}
      <div className="pv3-foot">
        <Link to="/leaderboard" className="pv3-foot-link">← Zpět na leaderboard</Link>
        <span className="pv3-foot-rule" />
        <span className="pv3-foot-tag">PROFILE · v3</span>
      </div>
    </div>
  );
}

/* ──────────────── Sub-components ──────────────── */

function Stat({ label, value, icon, suffix, highlight }) {
  const numeric = typeof value === 'number' ? value : parseInt(value, 10);
  const hasNum = !isNaN(numeric);
  const animated = useCountUp(hasNum ? numeric : 0);
  return (
    <div className={`pv3-stat${highlight ? ' is-hi' : ''}`}>
      <span className="pv3-stat-ic">{icon}</span>
      <span className="pv3-stat-val">
        {hasNum ? animated : '—'}
        {suffix && hasNum && <small>{suffix}</small>}
      </span>
      <span className="pv3-stat-label">{label}</span>
    </div>
  );
}

function EmptyState({ icon, title, hint, ctaTo, ctaLabel }) {
  return (
    <div className="pv3-empty">
      <div className="pv3-empty-icon" aria-hidden="true">{icon}</div>
      <div className="pv3-empty-title">{title}</div>
      <div className="pv3-empty-hint">{hint}</div>
      {ctaTo && (
        <Link to={ctaTo} className="pv3-empty-cta">{ctaLabel}</Link>
      )}
    </div>
  );
}

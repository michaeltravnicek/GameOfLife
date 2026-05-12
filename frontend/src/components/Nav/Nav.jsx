import { useEffect, useRef, useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './Nav.css';

const initials = (s) =>
  (s || '').split(' ').map((w) => w[0]).filter(Boolean).join('').slice(0, 2).toUpperCase() || '?';

function activeKey(pathname) {
  if (pathname === '/') return 'home';
  if (pathname.startsWith('/akce')) return 'events';
  if (pathname.startsWith('/galerie')) return 'gallery';
  if (pathname.startsWith('/leaderboard')) return 'leaderboard';
  if (pathname.startsWith('/profil')) return 'profile';
  return '';
}

export default function Nav() {
  const { user } = useAuth();
  const location = useLocation();
  const page = activeKey(location.pathname);
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);
  const upRef = useRef(0);

  useEffect(() => {
    const onScroll = () => {
      const y = window.pageYOffset;
      if (y > lastY.current) {
        upRef.current = 0;
        setHidden(true);
      } else {
        upRef.current += 1;
        if (upRef.current >= 3) {
          setHidden(false);
          upRef.current = 0;
        }
      }
      lastY.current = y <= 0 ? 0 : y;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const navItem = (to, label, key) => (
    <NavLink to={to} className={`nav-item${page === key ? ' active' : ''}`}>
      {label}
    </NavLink>
  );

  const profileHref = user ? `/profil/${user.username}` : '/prihlasit';
  const displayName = user?.full_name || user?.username || '';

  return (
    <nav className={`top${hidden ? ' hidden' : ''}`} id="gol-nav">
      <div className="nav-left">
        {navItem('/', 'Domů', 'home')}
        {navItem('/akce', 'Akce', 'events')}
        {navItem('/galerie', 'Galerie', 'gallery')}
      </div>
      <Link to="/" className="nav-logo" aria-label="Game of Life">
        <img src="/assets/gameoflive-onrender-com-english-us-by-html-to-design-free-version-0905-gol-logo-bw-1.svg" alt="Game of Life" />
      </Link>
      <div className="nav-right">
        {navItem('/leaderboard', 'Leaderboard', 'leaderboard')}
        {user ? (
          <>
            <Link
              to={profileHref}
              className={`nav-avatar${page === 'profile' ? ' active' : ''}`}
              title={displayName}
            >
              {user.photo ? <img src={user.photo} alt={displayName} /> : initials(displayName)}
            </Link>
          </>
        ) : (
          <Link to="/registrace" className="nav-btn-start">Start Playing ➤</Link>
        )}
      </div>
    </nav>
  );
}

import { useEffect, useRef, useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { preloadRoute } from '../../services/routePreload';
import StartPlayingButton from '../StartPlayingButton/StartPlayingButton';
import './Nav.css';

const initials = (s) =>
  (s || '').split(' ').map((w) => w[0]).filter(Boolean).join('').slice(0, 2).toUpperCase() || '?';

function activeKey(pathname) {
  if (pathname === '/') return 'home';
  if (pathname.startsWith('/akce')) return 'events';
  if (pathname.startsWith('/galerie')) return 'gallery';
  if (pathname.startsWith('/leaderboard')) return 'leaderboard';
  if (pathname.startsWith('/profil')) return 'profile';
  if (pathname.startsWith('/historie')) return 'historie';
  return '';
}

export default function Nav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const page = activeKey(location.pathname);
  const [hidden, setHidden] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
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

  // Close mobile menu on navigation
  useEffect(() => {
    setMenuOpen(false);
    document.body.style.overflow = '';
  }, [location.pathname]);

  // Close on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closeMenu(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  // Always release body scroll lock on unmount (in case Nav is removed mid-open)
  useEffect(() => () => { document.body.style.overflow = ''; }, []);

  const openMenu = () => { setMenuOpen(true); document.body.style.overflow = 'hidden'; };
  const closeMenu = () => { setMenuOpen(false); document.body.style.overflow = ''; };

  // Preload chunk + data when the user signals intent (hover / keyboard focus).
  // By the time they click, the route's JS + first API response are usually
  // already cached, so navigation feels instant.
  const handlePreload = (to) => () => preloadRoute(to);

  const navItem = (to, label, key) => (
    <NavLink
      to={to}
      className={`nav-item${page === key ? ' active' : ''}`}
      onMouseEnter={handlePreload(to)}
      onFocus={handlePreload(to)}
    >
      {label}
    </NavLink>
  );

  const profileHref = user ? `/profil/${user.username}` : '/prihlasit';
  const displayName = user?.full_name || user?.username || '';

  return (
    <>
      <nav className={`top${hidden ? ' hidden' : ''}`} id="gol-nav">
        <div className="nav-left">
          {navItem('/', 'Domů', 'home')}
          {navItem('/akce', 'Akce', 'events')}
          {navItem('/galerie', 'Galerie', 'gallery')}
          {navItem('/leaderboard', 'Leaderboard', 'leaderboard')}
          {navItem('/historie', 'Historie', 'historie')}
        </div>
        <Link to="/" className="nav-logo" aria-label="Game of Life">
          <img src="/assets/gameoflive-onrender-com-english-us-by-html-to-design-free-version-0905-gol-logo-bw-1.svg" alt="Game of Life" />
        </Link>
        <div className="nav-right">
          {user ? (
            <Link
              to={profileHref}
              className={`nav-avatar${page === 'profile' ? ' active' : ''}`}
              title={displayName}
            >
              {user.photo ? <img src={user.photo} alt={displayName} /> : initials(displayName)}
            </Link>
          ) : (
            <StartPlayingButton />
          )}
          <button
            className="nav-hamburger"
            onClick={openMenu}
            aria-label="Otevřít menu"
          >☰</button>
        </div>
      </nav>

      {/* Full-screen mobile menu overlay */}
      <div
        className={`nav-mobile-menu${menuOpen ? ' open' : ''}`}
        onClick={(e) => { if (e.target === e.currentTarget) closeMenu(); }}
      >
        <button className="nav-mob-close" onClick={closeMenu} aria-label="Zavřít menu">×</button>
        <Link className="nav-mob-item" to="/">Domů</Link>
        <Link className="nav-mob-item" to="/akce">Akce</Link>
        <Link className="nav-mob-item" to="/galerie">Galerie</Link>
        <Link className="nav-mob-item" to="/leaderboard">Leaderboard</Link>
        <Link className="nav-mob-item" to="/historie">Historie</Link>
        {user ? (
          <>
            <Link className="nav-mob-item" to={profileHref}>Profil ({displayName})</Link>
            {logout && (
              <button
                className="nav-mob-item"
                style={{ color: 'rgba(255,255,255,.45)' }}
                onClick={() => { closeMenu(); logout(); }}
              >Odhlásit se</button>
            )}
          </>
        ) : (
          <>
            <Link className="nav-mob-item" to="/prihlasit">Přihlásit se</Link>
            <Link className="nav-mob-item nav-mob-start" to="/registrace">Start Playing ➤</Link>
          </>
        )}
      </div>
    </>
  );
}

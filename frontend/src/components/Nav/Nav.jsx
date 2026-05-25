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
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const lastY = useRef(0);
  const upRef = useRef(0);
  const navRef = useRef(null);
  const userRef = useRef(null);

  const closeMenu = () => setMenuOpen(false);

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

  // On navigation: close menus and make sure the nav is visible at the top of
  // the freshly-loaded page (the page also scrolls to 0).
  useEffect(() => {
    setMenuOpen(false);
    setUserMenuOpen(false);
    setHidden(false);
    lastY.current = 0;
    upRef.current = 0;
  }, [location.pathname]);

  // Close on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') { setMenuOpen(false); setUserMenuOpen(false); } };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  // Close the avatar dropdown when clicking outside it.
  useEffect(() => {
    if (!userMenuOpen) return undefined;
    const onClick = (e) => {
      if (userRef.current && !userRef.current.contains(e.target)) setUserMenuOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [userMenuOpen]);

  // Close the mobile dropdown when tapping anywhere outside the nav.
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onClick = (e) => {
      if (navRef.current && !navRef.current.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [menuOpen]);

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

  const dropItem = (to, label, key) => (
    <Link
      to={to}
      className={`nav-drop-item${page === key ? ' active' : ''}`}
      role="menuitem"
      onClick={closeMenu}
      onMouseEnter={handlePreload(to)}
    >
      {label}
    </Link>
  );

  const profileHref = user ? `/profil/${user.username}` : '/prihlasit';
  const displayName = user?.full_name || user?.username || '';

  return (
    <nav className={`top${hidden ? ' hidden' : ''}`} id="gol-nav" ref={navRef}>
      <div className="nav-left">
        <button
          className="nav-hamburger"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label="Menu"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
        >☰</button>
        {navItem('/', 'Domů', 'home')}
        {navItem('/akce', 'Akce', 'events')}
        {navItem('/galerie', 'Galerie', 'gallery')}
      </div>
      <Link to="/" className="nav-logo" aria-label="Game of Life">
        <img src="/assets/gameoflive-onrender-com-english-us-by-html-to-design-free-version-0905-gol-logo-bw-1.svg" alt="Game of Life" />
      </Link>
      <div className="nav-right">
        {navItem('/leaderboard', 'Leaderboard', 'leaderboard')}
        {navItem('/historie', 'Historie', 'historie')}
        {user ? (
          <div className="nav-user" ref={userRef}>
            <button
              type="button"
              className={`nav-avatar${page === 'profile' ? ' active' : ''}`}
              title={displayName}
              aria-haspopup="menu"
              aria-expanded={userMenuOpen}
              onClick={() => setUserMenuOpen((o) => !o)}
            >
              {user.photo ? <img src={user.photo} alt={displayName} /> : initials(displayName)}
            </button>
            <div className={`nav-user-menu${userMenuOpen ? ' open' : ''}`} role="menu">
              <div className="nav-user-name">{displayName}</div>
              <Link className="nav-user-item" role="menuitem" to={profileHref}>Profil</Link>
              <button
                type="button"
                className="nav-user-item nav-user-logout"
                role="menuitem"
                onClick={() => { setUserMenuOpen(false); logout(); }}
              >Odhlásit se</button>
            </div>
          </div>
        ) : (
          <StartPlayingButton />
        )}
      </div>

      {/* Full-width mobile dropdown — same popup style as the avatar menu. */}
      <div className={`nav-drop${menuOpen ? ' open' : ''}`} role="menu">
        {user && <div className="nav-drop-name">{displayName}</div>}
        {dropItem('/', 'Domů', 'home')}
        {dropItem('/akce', 'Akce', 'events')}
        {dropItem('/galerie', 'Galerie', 'gallery')}
        {dropItem('/leaderboard', 'Leaderboard', 'leaderboard')}
        {dropItem('/historie', 'Historie', 'historie')}
        {user ? (
          <>
            {dropItem(profileHref, 'Profil', 'profile')}
            {logout && (
              <button
                type="button"
                className="nav-drop-item nav-drop-logout"
                role="menuitem"
                onClick={() => { closeMenu(); logout(); }}
              >Odhlásit se</button>
            )}
          </>
        ) : (
          <>
            <Link className="nav-drop-item" role="menuitem" to="/prihlasit" onClick={closeMenu}>Přihlásit se</Link>
            <Link className="nav-drop-item nav-drop-start" role="menuitem" to="/registrace" onClick={closeMenu}>Start Playing ➤</Link>
          </>
        )}
      </div>
    </nav>
  );
}

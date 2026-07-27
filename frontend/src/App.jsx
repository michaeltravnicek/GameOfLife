import { lazy, Suspense, useEffect, useRef } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import Nav from './components/Nav/Nav';
import Footer from './components/Footer/Footer';

// Eager: only the home page. Everything else is split into its own chunk
// and downloaded on-demand the first time the route is visited.
import HomePage from './pages/Home/HomePage';

const EventsPage = lazy(() => import('./pages/Events/EventsPage'));
const EventDetailPage = lazy(() => import('./pages/EventDetail/EventDetailPage'));
const CreateEventPage = lazy(() => import('./pages/Events/CreateEventPage'));
const EditEventPage = lazy(() => import('./pages/Events/EditEventPage'));
const GalleryPage = lazy(() => import('./pages/Gallery/GalleryPage'));
const LeaderboardPage = lazy(() => import('./pages/Leaderboard/LeaderboardPage'));
const ProfilePage = lazy(() => import('./pages/Profile/ProfilePage'));
const EditProfilePage = lazy(() => import('./pages/Profile/EditProfilePage'));
const LoginPage = lazy(() => import('./pages/Login/LoginPage'));
const RegisterPage = lazy(() => import('./pages/Register/RegisterPage'));
const PrivacyPage = lazy(() => import('./pages/Privacy/PrivacyPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPassword/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPassword/ResetPasswordPage'));
const PlayerPage = lazy(() => import('./pages/Player/PlayerPage'));
const FeedbacksPage = lazy(() => import('./pages/Admin/FeedbacksPage'));
const OBodechPage = lazy(() => import('./pages/OBodech/OBodechPage'));
const HistoriePage = lazy(() => import('./pages/Historie/HistoriePage'));

function ScrollToTop() {
  const location = useLocation();
  const prevPath = useRef(location.pathname);
  useEffect(() => {
    // Leave in-page anchor links (#section) to the browser.
    if (location.hash) { prevPath.current = location.pathname; return; }
    // Depending on the whole location (not just pathname) means this also runs
    // when you click the current page's own nav link — React Router emits a
    // fresh location key even for a same-path navigation. Smooth-scroll when
    // we're already on the page (a visible ride to the top); jump instantly for
    // real page-to-page navigation so new content starts at the top at once.
    const samePage = prevPath.current === location.pathname;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: samePage && !reduce ? 'smooth' : 'auto' });
    prevPath.current = location.pathname;
  }, [location]);
  return null;
}

function Layout({ children, withChrome = true }) {
  return (
    <div className="app-shell">
      {withChrome && <a className="gol-skip-link" href="#obsah">Přeskočit na obsah</a>}
      {withChrome && <Nav />}
      <main id="obsah" className="app-main">{children}</main>
      {withChrome && <Footer />}
    </div>
  );
}

function RouteFallback() {
  return (
    <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,241,212,.55)', fontFamily: 'var(--font-mono)', fontStyle: 'italic', fontSize: 14, letterSpacing: '.14em' }}>
      Načítám…
    </div>
  );
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<Layout><HomePage /></Layout>} />
          <Route path="/events" element={<Layout><EventsPage /></Layout>} />
          <Route path="/events/:slug/upravit" element={<Layout><EditEventPage /></Layout>} />
          <Route path="/events/vytvorit" element={<Layout><CreateEventPage /></Layout>} />
          <Route path="/events/:slug" element={<Layout><EventDetailPage /></Layout>} />
          <Route path="/galerie" element={<Layout><GalleryPage /></Layout>} />
          <Route path="/leaderboard" element={<Layout><LeaderboardPage /></Layout>} />
          <Route path="/profil" element={<Layout><ProfilePage /></Layout>} />
          <Route path="/profil/:username" element={<Layout><ProfilePage /></Layout>} />
          <Route path="/upravit-profil" element={<Layout><EditProfilePage /></Layout>} />
          <Route path="/o-bodech" element={<Layout><OBodechPage /></Layout>} />
          <Route path="/historie" element={<Layout><HistoriePage /></Layout>} />
          <Route path="/prihlasit" element={<Layout><LoginPage /></Layout>} />
          <Route path="/registrace" element={<Layout><RegisterPage /></Layout>} />
          <Route path="/ochrana-osobnich-udaju" element={<Layout><PrivacyPage /></Layout>} />
          <Route path="/zapomenute-heslo" element={<Layout><ForgotPasswordPage /></Layout>} />
          <Route path="/obnova-hesla/:uid/:token" element={<Layout><ResetPasswordPage /></Layout>} />
          <Route path="/hrac/:userId" element={<Layout><PlayerPage /></Layout>} />
          <Route path="/sprava/zpetna-vazba" element={<Layout><FeedbacksPage /></Layout>} />
        </Routes>
      </Suspense>
    </>
  );
}

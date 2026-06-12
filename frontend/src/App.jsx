import { lazy, Suspense, useEffect } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import Nav from './components/Nav/Nav';
import Footer from './components/Footer/Footer';

// Eager: only the home page. Everything else is split into its own chunk
// and downloaded on-demand the first time the route is visited.
import HomePage from './pages/Home/HomePage';

const HomePageAlt = lazy(() => import('./pages/Home/HomePageAlt'));
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
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPassword/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPassword/ResetPasswordPage'));
const PlayerPage = lazy(() => import('./pages/Player/PlayerPage'));
const FeedbacksPage = lazy(() => import('./pages/Admin/FeedbacksPage'));
const OBodechPage = lazy(() => import('./pages/OBodech/OBodechPage'));
const HistoriePage = lazy(() => import('./pages/Historie/HistoriePage'));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function Layout({ children, withChrome = true }) {
  return (
    <div className="app-shell">
      {withChrome && <Nav />}
      <main className="app-main">{children}</main>
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
          <Route path="/alt" element={<Layout><HomePageAlt /></Layout>} />
          <Route path="/akce" element={<Layout><EventsPage /></Layout>} />
          <Route path="/akce/:slug/upravit" element={<Layout><EditEventPage /></Layout>} />
          <Route path="/akce/vytvorit" element={<Layout><CreateEventPage /></Layout>} />
          <Route path="/akce/:slug" element={<Layout><EventDetailPage /></Layout>} />
          <Route path="/galerie" element={<Layout><GalleryPage /></Layout>} />
          <Route path="/leaderboard" element={<Layout><LeaderboardPage /></Layout>} />
          <Route path="/profil" element={<Layout><ProfilePage /></Layout>} />
          <Route path="/profil/:username" element={<Layout><ProfilePage /></Layout>} />
          <Route path="/upravit-profil" element={<Layout><EditProfilePage /></Layout>} />
          <Route path="/o-bodech" element={<Layout><OBodechPage /></Layout>} />
          <Route path="/historie" element={<Layout><HistoriePage /></Layout>} />
          <Route path="/prihlasit" element={<Layout><LoginPage /></Layout>} />
          <Route path="/registrace" element={<Layout><RegisterPage /></Layout>} />
          <Route path="/zapomenute-heslo" element={<Layout><ForgotPasswordPage /></Layout>} />
          <Route path="/obnova-hesla/:uid/:token" element={<Layout><ResetPasswordPage /></Layout>} />
          <Route path="/hrac/:userId" element={<Layout><PlayerPage /></Layout>} />
          <Route path="/sprava/zpetna-vazba" element={<Layout><FeedbacksPage /></Layout>} />
        </Routes>
      </Suspense>
    </>
  );
}

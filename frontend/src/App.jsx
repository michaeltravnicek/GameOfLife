import { Routes, Route, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Nav from './components/Nav/Nav';
import Footer from './components/Footer/Footer';
import HomePage from './pages/Home/HomePage';
import EventsPage from './pages/Events/EventsPage';
import EventDetailPage from './pages/EventDetail/EventDetailPage';
import GalleryPage from './pages/Gallery/GalleryPage';
import LeaderboardPage from './pages/Leaderboard/LeaderboardPage';
import ProfilePage from './pages/Profile/ProfilePage';
import LoginPage from './pages/Login/LoginPage';
import RegisterPage from './pages/Register/RegisterPage';
import OBodechPage from './pages/OBodech/OBodechPage';

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

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Layout><HomePage /></Layout>} />
        <Route path="/akce" element={<Layout><EventsPage /></Layout>} />
        <Route path="/akce/:slug" element={<Layout><EventDetailPage /></Layout>} />
        <Route path="/galerie" element={<Layout><GalleryPage /></Layout>} />
        <Route path="/leaderboard" element={<Layout><LeaderboardPage /></Layout>} />
        <Route path="/profil" element={<Layout><ProfilePage /></Layout>} />
        <Route path="/profil/:username" element={<Layout><ProfilePage /></Layout>} />
        <Route path="/o-bodech" element={<Layout><OBodechPage /></Layout>} />
        <Route path="/prihlasit" element={<Layout withChrome={false}><LoginPage /></Layout>} />
        <Route path="/registrace" element={<Layout withChrome={false}><RegisterPage /></Layout>} />
      </Routes>
    </>
  );
}

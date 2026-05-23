import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchHome } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import EventCard from '../../components/EventCard/EventCard';
import Avatar from '../../components/Avatar/Avatar';
import Hero from '../../components/Hero/Hero';
import CheckinBanner from '../../components/CheckinBanner/CheckinBanner';
import './HomePage.css';

const FALLBACK_GAL = ['/gallery/gal0.jpg', '/gallery/gal1.jpg', '/gallery/gal2.jpg', '/gallery/gal3.jpg'];
const FALLBACK_HERO_SLIDES = FALLBACK_GAL.map((url, i) => ({ url, name: '', slug: '', date: null, _i: i }));

// Hoisted: this used to live inside a `.map(...)` callback and was rebuilt
// for every leaderboard row on every render.
const TROPHIES = { 1: '🏆', 2: '🥈', 3: '🥉' };

// Static row style — extracted so React skips diffing on every render.
const LB_ROW_LINK_STYLE = { textDecoration: 'none', color: 'inherit' };

const INITIAL_DATA = { hero_events: [], upcoming_events: [], top_players: [], about_stats: {} };

export default function HomePage() {
  const { data: payload } = useCachedQuery('home', fetchHome, { ttl: CACHE_TTL.HOME });
  const data = payload || INITIAL_DATA;
  const [galCur, setGalCur] = useState(0);

  // Stable references across renders — only recomputed when API data changes.
  const heroSlides = useMemo(
    () => (data.hero_events.length ? data.hero_events : FALLBACK_HERO_SLIDES),
    [data.hero_events],
  );
  const galImages = useMemo(
    () => (data.hero_events.length ? data.hero_events.map((h) => h.url) : FALLBACK_GAL),
    [data.hero_events],
  );

  const galN = galImages.length;
  const galPrev = useCallback(
    () => setGalCur((c) => (c - 1 + galN) % galN),
    [galN],
  );
  const galNext = useCallback(
    () => setGalCur((c) => (c + 1) % galN),
    [galN],
  );

  const stats = data.about_stats || {};

  return (
    <div className="home-page">

      <CheckinBanner events={data.active_checkin_events || []} />

      <Hero slides={heroSlides} ctaTo="/akce" ctaLabel="Zobrazit akce" />

      {/* UPCOMING EVENTS */}
      <section className="events-section">
        <h2 className="sec-title"><span className="star">✦</span> Nadcházející akce <span className="star">✦</span></h2>
        <div className="events-grid">
          {data.upcoming_events.length === 0 && (
            <p className="events-empty">Žádné nadcházející akce. Sleduj nás na sítích!</p>
          )}
          {data.upcoming_events.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </div>
      </section>

      {/* LEADERBOARD */}
      <section className="lb-section">
        <div className="lb-bg" />
        <div className="lb-tint" />
        <div className="lb-inner">
          <h2 className="lb-title"><span className="tr">🏆</span> Top hráči <span className="tr">🏆</span></h2>
          <div className="lb-card">
            <div className="lb-head"><div>#</div><div>hráč</div><div className="lb-head-pts">pts</div></div>
            {data.top_players.map((p) => {
              const isTop = p.rank <= 3;
              const link = p.profile_username ? `/profil/${p.profile_username}` : null;
              const Row = link ? Link : 'div';
              return (
                <Row
                  key={p.id}
                  to={link || undefined}
                  className="lb-row"
                  style={link ? LB_ROW_LINK_STYLE : undefined}
                >
                  <span className={`lb-rank${isTop ? ' top' : ''}`}>
                    {TROPHIES[p.rank] || `${p.rank}.`}
                  </span>
                  <div className="lb-name"><Avatar name={p.name} size="xs" className="lb-av" />{p.name}</div>
                  <div className="lb-pts">{p.total_points}</div>
                </Row>
              );
            })}
          </div>
        </div>
      </section>

      {/* ABOUT */}
      <section className="about-section">
        <div className="about-inner">
          <div className="about-photo">
            <img src="/gallery/gal3.jpg" alt="Game of Life komunita" loading="lazy" />
          </div>
          <div className="about-content">
            <div className="about-eyebrow">— O nás —</div>
            <h3 className="about-heading">Komunita, která hraje život naplno</h3>
            <p className="about-body">
              <strong>Game of Life</strong> je celoroční komunitní hra plná zábavy, výzev a nezapomenutelných
              zážitků. Vzešla z přesvědčení, že nejlepší okamžiky nevznikají samy — ale když se správní
              lidé potkají ve správný čas.
            </p>
            <p className="about-body">
              Každý event je bodovaný. Každá výzva tě posune dál. Nejde jen o body — jde o přátelství,
              vzpomínky a odvahu vyzkoušet něco nového.
            </p>
            <div className="stats-row">
              <div className="stat-item"><div className="stat-num">{stats.players ?? '—'}</div><div className="stat-label">Hráčů</div></div>
              <div className="stat-item"><div className="stat-num">{stats.events ?? '—'}</div><div className="stat-label">Events</div></div>
              <div className="stat-item"><div className="stat-num">{stats.points ?? '—'}</div><div className="stat-label">Bodů</div></div>
            </div>
            <div className="about-cta">
              <Link to="/historie" className="btn-pill">Číst historii <span className="arr"></span></Link>
            </div>
          </div>
        </div>
      </section>

      {/* GALLERY */}
      <section className="gallery-section">
        <div className="gal-header">
          <h2 className="gal-title"><span className="gal-star">📷</span> Galerie <span className="gal-star">📷</span></h2>
        </div>
        <div className="gal-container">
          <div
            className="gal-side"
            onClick={galPrev}
            style={{ backgroundImage: `url('${galImages[(galCur - 1 + galN) % galN]}')` }}
          />
          <div className="gal-main" style={{ backgroundImage: `url('${galImages[galCur]}')` }} />
          <div
            className="gal-side"
            onClick={galNext}
            style={{ backgroundImage: `url('${galImages[(galCur + 1) % galN]}')` }}
          />
        </div>
        <div className="gal-footer">
          <Link to="/galerie" className="btn-pill">Celá galerie <span className="arr"></span></Link>
        </div>
      </section>

    </div>
  );
}

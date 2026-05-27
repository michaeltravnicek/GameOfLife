import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchHero, fetchStats, fetchCheckinEvents, fetchEvents, fetchLeaderboard,
} from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL, PAGE_SIZE_EVENTS } from '../../constants/config';
import EventCard from '../../components/EventCard/EventCard';
import Hero from '../../components/Hero/Hero';
import CheckinBanner from '../../components/CheckinBanner/CheckinBanner';
import Button from '../../components/Button/Button';
import PlayerRow from '../../components/PlayerRow/PlayerRow';
import { useReveal } from '../../hooks/useReveal';
import './HomePage.css';

const FALLBACK_GAL = ['/gallery/gal0.jpg', '/gallery/gal1.jpg', '/gallery/gal2.jpg', '/gallery/gal3.jpg'];
const FALLBACK_HERO_SLIDES = FALLBACK_GAL.map((url, i) => ({ url, name: '', slug: '', date: null, _i: i }));

const EMPTY = [];
const HOME_TOP_PLAYERS = 10;

export default function HomePage() {
  // The old monolithic /home/ endpoint is gone — the page now composes several
  // independent, individually-cached endpoints. They fetch in parallel (each
  // useCachedQuery fires its own request), so there's no waterfall.
  const { data: hero } = useCachedQuery('hero', fetchHero, { ttl: CACHE_TTL.HOME });
  const { data: statsData } = useCachedQuery('stats', fetchStats, { ttl: CACHE_TTL.HOME });
  const { data: checkin } = useCachedQuery('checkin-events', fetchCheckinEvents, { ttl: CACHE_TTL.EVENT_DETAIL });
  const { data: upcomingData } = useCachedQuery(
    'events:upcoming|Vše|',
    () => fetchEvents({ limit: PAGE_SIZE_EVENTS, offset: 0, period: 'upcoming' }),
    { ttl: CACHE_TTL.EVENTS },
  );
  const { data: lbData } = useCachedQuery(
    'leaderboard:home',
    () => fetchLeaderboard('active', { limit: HOME_TOP_PLAYERS }),
    { ttl: CACHE_TTL.LEADERBOARD },
  );

  const [galCur, setGalCur] = useState(0);

  // Scroll-reveal refs — each section fades/staggers in as it enters view.
  const [evTitleRef, evTitleIn] = useReveal();
  const [evGridRef, evGridIn] = useReveal();
  const [lbTitleRef, lbTitleIn] = useReveal();
  const [lbCardRef, lbCardIn] = useReveal();
  const [aboutRef, aboutIn] = useReveal();
  const [galHeadRef, galHeadIn] = useReveal();
  const [galRef, galIn] = useReveal();

  const heroEvents = hero?.hero_events || EMPTY;
  const upcomingEvents = upcomingData?.events || EMPTY;
  const topPlayers = lbData?.entries || EMPTY;
  const checkinEvents = checkin?.events || EMPTY;
  const stats = statsData || {};

  // Stable references across renders — only recomputed when API data changes.
  const heroSlides = useMemo(
    () => (heroEvents.length ? heroEvents : FALLBACK_HERO_SLIDES),
    [heroEvents],
  );
  const galImages = useMemo(
    () => (heroEvents.length ? heroEvents.map((h) => h.url) : FALLBACK_GAL),
    [heroEvents],
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

  return (
    <div className="home-page">

      <CheckinBanner events={checkinEvents} />

      <Hero slides={heroSlides} ctaTo="/akce" ctaLabel="Zobrazit akce" />

      {/* UPCOMING EVENTS */}
      <section className="events-section">
        <h2 ref={evTitleRef} className={`sec-title reveal${evTitleIn ? ' in' : ''}`}><span className="star">✦</span> Nadcházející akce <span className="star">✦</span></h2>
        <div ref={evGridRef} className={`events-grid reveal-stagger${evGridIn ? ' in' : ''}`}>
          {upcomingEvents.length === 0 && (
            <p className="events-empty">Žádné nadcházející akce. Sleduj nás na sítích!</p>
          )}
          {upcomingEvents.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </div>
      </section>

      {/* LEADERBOARD */}
      <section className="lb-section">
        <div className="lb-bg" />
        <div className="lb-tint" />
        <div className="lb-inner">
          <h2 ref={lbTitleRef} className={`lb-title reveal${lbTitleIn ? ' in' : ''}`}><span className="tr">🏆</span> Top hráči <span className="tr">🏆</span></h2>
          <div ref={lbCardRef} className={`lb-card reveal-stagger${lbCardIn ? ' in' : ''}`}>
            <div className="lb-head"><div>#</div><div>hráč</div><div className="lb-head-pts">pts</div></div>
            {topPlayers.map((p) => (
              <PlayerRow key={p.id} player={p} />
            ))}
          </div>
        </div>
      </section>

      {/* ABOUT */}
      <section className="about-section">
        <div ref={aboutRef} className={`about-inner reveal${aboutIn ? ' in' : ''}`}>
          <div className="about-photo">
            <img src="/gallery/home-onas.jpg" alt="Game of Life komunita" loading="lazy" />
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
              <Button as="link" to="/historie" size="lg">Číst historii <span className="arr" /></Button>
            </div>
          </div>
        </div>
      </section>

      {/* GALLERY */}
      <section className="gallery-section">
        <div ref={galHeadRef} className={`gal-header reveal${galHeadIn ? ' in' : ''}`}>
          <h2 className="gal-title"><span className="gal-star">📷</span> Galerie <span className="gal-star">📷</span></h2>
        </div>
        <div ref={galRef} className={`gal-container reveal${galIn ? ' in' : ''}`}>
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
          <Button as="link" to="/galerie" size="lg">Celá galerie <span className="arr" /></Button>
        </div>
      </section>

    </div>
  );
}

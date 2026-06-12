import { useMemo } from 'react';
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
import GalleryCarousel from '../../components/GalleryCarousel/GalleryCarousel';
import { useReveal } from '../../hooks/useReveal';
import { useParallax } from '../../hooks/useParallax';
import { useCountUp } from '../../hooks/useCountUp';
import { galVariant } from '../../utils/img';
import './HomePage.css';
import './HomePageAlt.css';

const FALLBACK_GAL = ['gal0', 'gal1', 'gal2', 'gal3'].map(galVariant);
const FALLBACK_HERO_SLIDES = FALLBACK_GAL.map((url, i) => ({ url, name: '', slug: '', date: null, _i: i }));

const EMPTY = [];
const HOME_TOP_PLAYERS = 10;

/**
 * Experimental, motion-rich variant of HomePage (route: /alt). Same data, same
 * sections — adds hero parallax, count-up stats, directional reveals, a parallax
 * leaderboard backdrop, and the sliding GalleryCarousel. Kept separate so the
 * live homepage at / stays untouched while comparing.
 */
export default function HomePageAlt() {
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

  // Scroll-reveal refs — each section fades/slides in as it enters view.
  const [evTitleRef, evTitleIn] = useReveal();
  const [evGridRef, evGridIn] = useReveal();
  const [lbTitleRef, lbTitleIn] = useReveal();
  const [lbCardRef, lbCardIn] = useReveal();
  const [aboutRef, aboutIn] = useReveal();
  const [aboutTextRef, aboutTextIn] = useReveal();
  const [galHeadRef, galHeadIn] = useReveal();

  // Parallax backdrop behind the leaderboard.
  const lbBgRef = useParallax({ speed: 0.12 });

  const heroEvents = hero?.hero_events || EMPTY;
  const upcomingEvents = upcomingData?.events || EMPTY;
  const topPlayers = lbData?.entries || EMPTY;
  const checkinEvents = checkin?.events || EMPTY;
  const stats = statsData || {};

  // Count-up stats — tween from 0 once the About section scrolls into view.
  const [playersRef, playersVal] = useCountUp(stats.players ?? '—');
  const [eventsRef, eventsVal] = useCountUp(stats.events ?? '—');
  const [pointsRef, pointsVal] = useCountUp(stats.points ?? '—');

  const heroSlides = useMemo(
    () => (heroEvents.length ? heroEvents : FALLBACK_HERO_SLIDES),
    [heroEvents],
  );
  const galImages = useMemo(
    () => (heroEvents.length ? heroEvents.map((h) => h.url) : FALLBACK_GAL),
    [heroEvents],
  );

  return (
    <div className="home-page home-page-alt">

      <CheckinBanner events={checkinEvents} />

      <Hero slides={heroSlides} ctaTo="/akce" ctaLabel="Zobrazit akce" parallax />

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
        <div ref={lbBgRef} className="lb-bg" />
        <div className="lb-tint" />
        <div className="lb-inner">
          <h2 ref={lbTitleRef} className={`lb-title reveal${lbTitleIn ? ' in' : ''}`}><span className="star">✦</span> Top hráči <span className="star">✦</span></h2>
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
        <div className="about-inner">
          <div ref={aboutRef} className={`about-photo reveal-left${aboutIn ? ' in' : ''}`}>
            <picture>
              <source media="(max-width: 768px)" srcSet="/img/home-onas-mobile.webp" />
              <img src="/img/home-onas-desktop.webp" alt="Game of Life komunita" loading="lazy" />
            </picture>
          </div>
          <div ref={aboutTextRef} className={`about-content reveal-right${aboutTextIn ? ' in' : ''}`}>
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
              <div className="stat-item"><div ref={playersRef} className="stat-num">{playersVal}</div><div className="stat-label">Hráčů</div></div>
              <div className="stat-item"><div ref={eventsRef} className="stat-num">{eventsVal}</div><div className="stat-label">Events</div></div>
              <div className="stat-item"><div ref={pointsRef} className="stat-num">{pointsVal}</div><div className="stat-label">Bodů</div></div>
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
          <h2 className="gal-title"><span className="gal-star">✦</span> Galerie <span className="gal-star">✦</span></h2>
        </div>
        <GalleryCarousel images={galImages} />
        <div className="gal-footer">
          <Button as="link" to="/galerie" size="lg">Celá galerie <span className="arr" /></Button>
        </div>
      </section>

    </div>
  );
}

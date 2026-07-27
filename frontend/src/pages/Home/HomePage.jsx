import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchHero, fetchCheckinEvents, fetchEvents, fetchLeaderboard,
} from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL, PAGE_SIZE_EVENTS } from '../../constants/config';
import EventCard from '../../components/EventCard/EventCard';
import Hero from '../../components/Hero/Hero';
import CheckinBanner from '../../components/CheckinBanner/CheckinBanner';
import Button from '../../components/Button/Button';
import PlayerRow from '../../components/PlayerRow/PlayerRow';
import { useReveal } from '../../hooks/useReveal';
import { galVariant } from '../../utils/img';
import './HomePage.css';

const FALLBACK_GAL = ['gal0', 'gal1', 'gal2', 'gal3'].map(galVariant);
const FALLBACK_HERO_SLIDES = FALLBACK_GAL.map((url, i) => ({ url, name: '', slug: '', date: null, _i: i }));

const EMPTY = [];
const HOME_TOP_PLAYERS = 10;

export default function HomePage() {
  // The old monolithic /home/ endpoint is gone — the page now composes several
  // independent, individually-cached endpoints. They fetch in parallel (each
  // useCachedQuery fires its own request), so there's no waterfall.
  const { data: hero } = useCachedQuery('hero', fetchHero, { ttl: CACHE_TTL.HOME });
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

  // Below-the-fold background images (leaderboard section photo, gallery
  // strip) hold off until the browser is idle, so the first hero image never
  // shares bandwidth with them on initial load. The hero cycle gives the rest
  // seconds of headroom anyway.
  const [bgReady, setBgReady] = useState(false);
  useEffect(() => {
    const w = window;
    const id = w.requestIdleCallback
      ? w.requestIdleCallback(() => setBgReady(true), { timeout: 2500 })
      : setTimeout(() => setBgReady(true), 1200);
    return () => (w.cancelIdleCallback ? w.cancelIdleCallback(id) : clearTimeout(id));
  }, []);

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

  // Infinite filmstrip. The images are laid out THREE times in a row
  // ([…imgs, …imgs, …imgs]); we keep the centred slide inside the middle copy,
  // so there's always a real neighbour peeking on both sides — even at the
  // "ends" — which is what makes it a ring buffer. `galPos` is an index into
  // that tripled row; after each move settles we silently jump (no transition)
  // back to the equivalent slide in the middle copy, which looks identical.
  const galLoop = useMemo(
    () => (galN > 1 ? [...galImages, ...galImages, ...galImages] : galImages),
    [galImages, galN],
  );
  const [galPos, setGalPos] = useState(galN > 1 ? galN : 0);
  const [galAnim, setGalAnim] = useState(true);
  const galSnapId = useRef(0);
  const GAL_SLIDE_MS = 600; // slightly over the .55s CSS transition

  // Recentre to the middle copy whenever the image set changes (data loads).
  useEffect(() => {
    setGalAnim(false);
    setGalPos(galN > 1 ? galN : 0);
  }, [galImages, galN]);

  const galGoTo = useCallback((pos) => {
    if (galN < 2) return;
    setGalAnim(true);
    setGalPos(pos);
    const id = ++galSnapId.current;
    // After the slide finishes, snap back into the middle copy (seamless: the
    // target slide shows the same image). Guarded so a newer click wins.
    setTimeout(() => {
      if (id !== galSnapId.current) return;
      setGalAnim(false);
      setGalPos((p) => ((p - galN) % galN + galN) % galN + galN);
    }, GAL_SLIDE_MS);
  }, [galN]);

  return (
    <div className="home-page">

      <CheckinBanner events={checkinEvents} />

      <Hero slides={heroSlides} ctaTo="/events" ctaLabel="Zobrazit akce" />

      {/* UPCOMING EVENTS */}
      <section className="events-section">
        <h2 ref={evTitleRef} className={`sec-title reveal${evTitleIn ? ' in' : ''}`}><span className="star sparkle">✨</span> Nadcházející akce <span className="star sparkle">✨</span></h2>
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
        <div className={`lb-bg${bgReady ? ' ready' : ''}`} />
        <div className="lb-tint" />
        <div className="lb-inner">
          <h2 ref={lbTitleRef} className={`lb-title reveal${lbTitleIn ? ' in' : ''}`}><span className="lb-trophy">🏆</span> Top 10 hráčů <span className="lb-trophy">🏆</span></h2>
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
            <picture>
              <source media="(max-width: 768px)" srcSet="/img/home-onas-mobile.webp" />
              <img src="/img/home-onas-desktop.webp" alt="Game of Life komunita" loading="lazy" />
            </picture>
          </div>
          <div className="about-content">
            <div className="gol-sec-eyebrow">— O nás —</div>
            <h3 className="about-heading">Komunita, která hraje život naplno</h3>
            <p className="about-body">
              <strong>Game of Life</strong> je celoroční komunitní hra plná zábavy, výzev a nezapomenutelných
              zážitků. Vzešla z přesvědčení, že život není jen o přežívání, ale o prožívání a je potřeba si ho
              užít naplno. A to my přesně v naši komunitě JoyMaxxeru děláme. 
            </p>
            <p className="about-body">
              Každý event je bodovaný. Každá výzva tě posune dál. Pojď hrát život jako hru, sbírej
              vzpomínky a odvahu vyzkoušet něco nového.
            </p>
            <div className="stats-row">
              <div className="stat-item"><div className="stat-num">300+</div><div className="stat-label">Hráčů</div></div>
              <div className="stat-item"><div className="stat-num">70+</div><div className="stat-label">Eventů</div></div>
              <div className="stat-item"><div className="stat-num">40000+</div><div className="stat-label">Bodů</div></div>
            </div>
          </div>
        </div>
      </section>

      {/* GALLERY */}
      <section className="gallery-section">
        <div ref={galHeadRef} className={`gal-header reveal${galHeadIn ? ' in' : ''}`}>
          <h2 className="gal-title"><span className="gal-cam">📷</span> Galerie <span className="gal-cam">📷</span></h2>
        </div>
        {/* One long row of bordered images; the row slides so the current image
            is centred, its neighbours peeking. Clicking a peeking neighbour
            moves the row to it. The transform centres slide `galPos`: half the
            viewport, minus half a slide, minus galPos whole slides (+ gaps). */}
        <div ref={galRef} className={`gal-viewport reveal${galIn ? ' in' : ''}`}>
          <div
            className={`gal-track${galAnim ? '' : ' no-anim'}`}
            style={{ transform: `translateX(calc(50vw - var(--gal-slide-w) / 2 - ${galPos} * (var(--gal-slide-w) + var(--gal-gap))))` }}
          >
            {galLoop.map((src, e) => (
              <button
                type="button"
                key={e}
                className="gal-slide"
                data-active={e === galPos}
                aria-current={e === galPos ? 'true' : undefined}
                aria-label={`Zobrazit fotku ${(e % galN) + 1} z ${galN}`}
                onClick={() => galGoTo(e)}
                style={bgReady ? { backgroundImage: `url('${src}')` } : undefined}
              />
            ))}
          </div>
        </div>
        <div className="gal-footer">
          <Button as="link" to="/galerie" size="lg">Celá galerie <span className="arr" /></Button>
        </div>
      </section>

    </div>
  );
}

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fmtDate } from '../../utils/date';
import Button from '../Button/Button';
import { HERO_AUTO_CYCLE_MS } from '../../constants/config';
import { useParallax } from '../../hooks/useParallax';
import { isMobileViewport } from '../../utils/img';
import HeroDots from './HeroDots';
import './Hero.css';

// Phones get the lighter backend-generated variant when one exists.
const slideUrl = (s) => (s && isMobileViewport() && s.url_mobile ? s.url_mobile : s?.url);

// Fade + lift the hero copy as the section scrolls up out of view.
const fadeHeroInner = (el, { rect, vh }) => {
  const p = Math.min(1, Math.max(0, -rect.top / (vh * 0.7)));
  el.style.opacity = String(1 - p);
  el.style.transform = `translate3d(0, ${(rect.top * 0.18).toFixed(1)}px, 0)`;
};

/**
 * One slide background. Memoized so the auto-cycle re-render only updates the
 * single slide whose `isActive` flipped — the rest skip re-render entirely.
 */
const HeroSlide = memo(function HeroSlide({ url, isActive }) {
  // `url` is undefined until the slide has been "reached" — until then we render
  // an empty div so the browser issues no image request (the deferred-load win).
  const style = useMemo(() => (url ? { backgroundImage: `url('${url}')` } : undefined), [url]);
  return <div className={`gol-hero__slide${isActive ? ' is-active' : ''}`} style={style} />;
});

const requestIdle = (cb) =>
  (typeof window !== 'undefined' && window.requestIdleCallback)
    ? window.requestIdleCallback(cb)
    : setTimeout(cb, 400);
const cancelIdle = (id) =>
  (typeof window !== 'undefined' && window.cancelIdleCallback)
    ? window.cancelIdleCallback(id)
    : clearTimeout(id);

/**
 * Full-width hero with cycling background slides + centered title and CTA.
 *
 * slides : Array<{ url, name?, slug?, date? }>
 * ctaTo  : router path for the button
 * ctaLabel
 * eyebrow
 * fallbackTitle
 * autoCycleMs : interval between slide changes (default 5000)
 */
export default function Hero({
  slides = [],
  ctaTo = '/events',
  ctaLabel = 'Zobrazit akce',
  eyebrow = '— Sezóna 2026 —',
  fallbackTitle = 'Game of Life',
  autoCycleMs = HERO_AUTO_CYCLE_MS,
  parallax = false,
}) {
  const [current, setCurrent] = useState(0);
  const currentRef = useRef(0);
  const n = slides.length;

  // Which slide images have been "reached" and may load. The active slide always
  // loads (see render); this set additionally keeps the just-shown slide loaded
  // through its cross-fade and pre-warms the upcoming one — so the homepage
  // fetches one hero image up front instead of all of them.
  const [loaded, setLoaded] = useState(() => new Set([0]));
  const markLoaded = useCallback((idx) => {
    setLoaded((prev) => {
      const k = n ? ((idx % n) + n) % n : 0;
      if (prev.has(k)) return prev;
      const s = new Set(prev);
      s.add(k);
      return s;
    });
  }, [n]);

  // Single entry point for changing slide (auto-cycle + dots). Keeps the outgoing
  // slide loaded for its fade-out and loads the incoming one. setState here is in
  // an event/timer callback, never synchronously in an effect body.
  const goTo = useCallback((to) => {
    markLoaded(currentRef.current); // outgoing — stays painted while it fades out
    markLoaded(to);                 // incoming
    currentRef.current = to;
    setCurrent(to);
  }, [markLoaded]);

  // Opt-in scroll parallax: background lags, copy fades/lifts. Off by default so
  // the live homepage's hero stays flat.
  const slidesRef = useParallax({ speed: 0.14, disabled: !parallax });
  const innerRef = useParallax({ apply: fadeHeroInner, disabled: !parallax });

  useEffect(() => {
    if (n < 2) return undefined;
    const t = setInterval(() => goTo((currentRef.current + 1) % n), autoCycleMs);
    return () => clearInterval(t);
  }, [n, autoCycleMs, goTo]);

  // Pre-warm the upcoming slide during idle time so its cross-fade is ready
  // without competing with the initial paint.
  useEffect(() => {
    if (n < 2) return undefined;
    const id = requestIdle(() => markLoaded(current + 1));
    return () => cancelIdle(id);
  }, [current, n, markLoaded]);

  const slide = slides[current];

  return (
    <section className={`gol-hero${parallax ? ' gol-hero--parallax' : ''}`}>
      <div className="gol-hero__slides" ref={slidesRef}>
        {slides.map((s, i) => (
          <HeroSlide
            key={s.slug || s.url || String(i)}
            url={(i === current || loaded.has(i)) ? slideUrl(s) : undefined}
            isActive={i === current}
          />
        ))}
      </div>

      <div className="gol-hero__overlay" />

      <div className="gol-hero__inner" ref={innerRef}>
        <div className="gol-hero__eyebrow">{eyebrow}</div>
        <h1 className="gol-hero__title">{slide?.name || fallbackTitle}</h1>
        {slide?.date && <p className="gol-hero__date">{fmtDate(slide.date)}</p>}
      </div>

      <div className="gol-hero__cta-wrap">
        <Button as="link" to={ctaTo} size="lg">
          {ctaLabel} <span className="arr" aria-hidden="true" />
        </Button>
      </div>

      <HeroDots count={slides.length} current={current} onChange={goTo} />
    </section>
  );
}

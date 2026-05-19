import { memo, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fmtDate } from '../../utils/date';
import HeroDots from './HeroDots';
import './Hero.css';

/**
 * One slide background. Memoized so the auto-cycle re-render only updates the
 * single slide whose `isActive` flipped — the rest skip re-render entirely.
 */
const HeroSlide = memo(function HeroSlide({ url, isActive }) {
  // Build the style object once per `url` (stable across active toggles).
  const style = useMemo(() => ({ backgroundImage: `url('${url}')` }), [url]);
  return <div className={`gol-hero__slide${isActive ? ' is-active' : ''}`} style={style} />;
});

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
  ctaTo = '/akce',
  ctaLabel = 'Zobrazit akce',
  eyebrow = '— Sezóna 2026 —',
  fallbackTitle = 'Game of Life',
  autoCycleMs = 5000,
}) {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    if (slides.length < 2) return undefined;
    const t = setInterval(() => setCurrent((c) => (c + 1) % slides.length), autoCycleMs);
    return () => clearInterval(t);
  }, [slides.length, autoCycleMs]);

  const slide = slides[current];

  return (
    <section className="gol-hero">
      <div className="gol-hero__slides">
        {slides.map((s, i) => (
          <HeroSlide
            key={s.slug || s.url || String(i)}
            url={s.url}
            isActive={i === current}
          />
        ))}
      </div>

      <div className="gol-hero__overlay" />

      <div className="gol-hero__inner">
        <div className="gol-hero__eyebrow">{eyebrow}</div>
        <h1 className="gol-hero__title">{slide?.name || fallbackTitle}</h1>
        {slide?.date && <p className="gol-hero__date">{fmtDate(slide.date)}</p>}
      </div>

      <Link to={ctaTo} className="gol-hero__cta">
        {ctaLabel} <span className="gol-hero__cta-arrow" aria-hidden="true" />
      </Link>

      <HeroDots count={slides.length} current={current} onChange={setCurrent} />
    </section>
  );
}

import { memo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fmtDate, MONTHS_SHORT } from '../../utils/date';
import { preloadEventDetail } from '../../services/routePreload';
import './EventCardAlt.css';

/* Small stroke icons (Lucide paths) — inherit currentColor so each variant
   tints them via its own text color. */
function IcoCal() {
  return (
    <svg className="evalt-ico" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}
function IcoPin() {
  return (
    <svg className="evalt-ico" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="3" />
    </svg>
  );
}
function IcoTrophy() {
  return (
    <svg className="evalt-ico" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" /><path d="M4 22h16" />
      <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" /><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
      <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
    </svg>
  );
}

/* ── Variant A: Frosted glass ──
   Dark translucent panel with backdrop blur over the page's photo backdrop.
   Glass pills for points/category, light sheen across the top edge. */
function FrostCard({ event }) {
  return (
    <>
      <img
        className="evalt-badge"
        src={event.logo || '/img/GOL_C50_transparent.webp'}
        alt=""
        loading="lazy"
        width="110"
        height="110"
      />
      <h3 className="evalt-title">{event.name}</h3>
      <div className="evalt-meta">
        <div><IcoCal />{fmtDate(event.date)}</div>
        <div><IcoPin />{event.place}</div>
      </div>
      <div className="evalt-footer">
        <div className="evalt-foot-tags">
          <span className="evalt-pts"><IcoTrophy />+{event.points} pts</span>
          {event.category?.name && <span className="evalt-cat">{event.category.name}</span>}
          <span className={`evalt-status${event.is_past ? ' done' : ''}`}>
            {event.is_past ? 'Proběhlo' : 'Akce'}
          </span>
        </div>
        <span className="evalt-detail">Detail →</span>
      </div>
    </>
  );
}

/* ── Variant B: Ticket stub ──
   Cream ticket with a perforated tear-off date block on the left
   (punched notches via CSS mask, dashed perforation line). */
function StubCard({ event }) {
  const d = event.date ? new Date(event.date) : null;
  return (
    <div className="stub-inner">
      <div className="stub-date" aria-hidden="true">
        <span className="stub-day">{d ? d.getDate() : '—'}</span>
        <span className="stub-month">{d ? MONTHS_SHORT[d.getMonth()] : ''}</span>
        <span className="stub-year">{d ? d.getFullYear() : ''}</span>
      </div>
      <div className="stub-main">
        <div className="stub-top">
          <span className="stub-brand">Game of Life</span>
          <span className={`evalt-status${event.is_past ? ' done' : ''}`}>
            {event.is_past ? 'Proběhlo' : 'Akce'}
          </span>
        </div>
        <h3 className="evalt-title">{event.name}</h3>
        <div className="evalt-meta">
          <div><IcoPin />{event.place}</div>
        </div>
        <div className="evalt-footer">
          <span className="evalt-pts"><IcoTrophy />+{event.points} pts</span>
          <span className="evalt-detail">Detail →</span>
        </div>
      </div>
    </div>
  );
}

/* ── Variant C: Poster ──
   Hard offset shadow (pressed on hover) + rotated points sticker.
   Shared markup for the color rotations: A purple/pink, B cream/purple
   ("paper print" — styling keyed off the evalt-poster-b root class). */
function PosterCard({ event }) {
  return (
    <>
      <span className="poster-pts" aria-hidden="true">+{event.points} pts</span>
      <span className="poster-eyebrow">Game of Life ★ {event.is_past ? 'Proběhlo' : 'Akce'}</span>
      <h3 className="evalt-title">{event.name}</h3>
      <div className="evalt-meta">
        <div><IcoCal />{fmtDate(event.date)}</div>
        <div><IcoPin />{event.place}</div>
      </div>
      <div className="evalt-footer">
        {event.category?.name && <span className="evalt-cat">{event.category.name}</span>}
        <span className="evalt-detail">Detail →</span>
      </div>
    </>
  );
}

/* ── Variant C2: Gig poster ──
   Blue print with a huge stacked date column on the right —
   the date is the poster's hero, gig-flyer style. */
function PosterDateCard({ event }) {
  const d = event.date ? new Date(event.date) : null;
  return (
    <div className="posterc-row">
      <div className="posterc-main">
        <span className="poster-eyebrow">Game of Life ★ {event.is_past ? 'Proběhlo' : 'Akce'}</span>
        <h3 className="evalt-title">{event.name}</h3>
        <div className="evalt-meta">
          <div><IcoPin />{event.place}</div>
        </div>
        <div className="evalt-footer">
          <span className="evalt-pts"><IcoTrophy />+{event.points} pts</span>
          <span className="evalt-detail">Detail →</span>
        </div>
      </div>
      <div className="posterc-date" aria-hidden="true">
        <span className="pc-day">{d ? d.getDate() : '—'}</span>
        <span className="pc-month">{d ? MONTHS_SHORT[d.getMonth()] : ''}</span>
        <span className="pc-year">{d ? d.getFullYear() : ''}</span>
      </div>
    </div>
  );
}

/* ── Variant C3: Marquee ──
   Pink centered layout — marquee line up top, stamped dark points
   label in the bottom bar. */
function PosterMarqueeCard({ event }) {
  return (
    <>
      <span className="posterd-marquee">★ Game of Life ★ {event.is_past ? 'Proběhlo' : 'Akce'} ★</span>
      <h3 className="evalt-title">{event.name}</h3>
      <div className="posterd-meta">{fmtDate(event.date)} · {event.place}</div>
      <div className="posterd-bar">
        <span className="posterd-pts">+{event.points} pts</span>
        <span className="evalt-detail">Detail →</span>
      </div>
    </>
  );
}

const VARIANTS = {
  frost: FrostCard,
  stub: StubCard,
  poster: PosterCard,
  'poster-b': PosterCard,
  'poster-c': PosterDateCard,
  'poster-d': PosterMarqueeCard,
};

/**
 * Alternative event card designs (design exploration — see EventsPage switcher).
 *
 * event   : { id, slug, name, date, place, points, logo, is_past, category? }
 * variant : 'frost' | 'stub' | 'poster'
 */
function EventCardAlt({ event, variant = 'frost' }) {
  const handlePreload = useCallback(() => preloadEventDetail(event.slug), [event.slug]);
  const Body = VARIANTS[variant] || FrostCard;
  return (
    <Link
      to={`/events/${event.slug}`}
      className={`evalt evalt-${variant}${event.is_past ? ' is-past' : ''}`}
      onMouseEnter={handlePreload}
      onFocus={handlePreload}
    >
      <Body event={event} />
    </Link>
  );
}

export default memo(EventCardAlt);

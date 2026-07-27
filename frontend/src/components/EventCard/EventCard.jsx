import { memo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fmtDate } from '../../utils/date';
import { preloadEventDetail } from '../../services/routePreload';
import DashedBorder from '../DashedBorder/DashedBorder';
import './EventCard.css';

function DarkCard({ event }) {
  return (
    <>
      <DashedBorder className="evcard-dark-frame" baseColor="transparent" dashColor="#fff" radius={16} width={2.5} dash={7} gap={12} />

      <div className="evcard-dark-inner">
        <div className="evcard-title-wrap">
          <div className="evcard-brand">Game of Life</div>
          <div className="evcard-title">{event.name}</div>
        </div>
        <div className="evcard-meta">
          <div className="ev-date"><span className="ev-emoji">📅</span>{fmtDate(event.date)}</div>
          <div className="ev-place"><span className="ev-emoji">📍</span>{event.place}</div>
          <div className="ev-pts-label"><span className="ev-emoji">🏆</span>+{event.points} pts</div>
        </div>
      </div>

      {/* The event's own logo; the neutral GOL mark when none is set (C50 is
          one specific event's brand, not a generic fallback). */}
      <img
        className="evcard-badge"
        src={event.logo || '/img/GOL_main_logo_pink.webp'}
        alt={event.name}
        loading="lazy"
        width="150"
        height="150"
        style={event.logo ? { '--logo-scale': event.logo_scale ?? 1 } : undefined}
      />
    </>
  );
}

/* Light theme = the poster skin (events page): opaque blue grain, solid black
   border, 3D ledge that presses down on hover, logo badge top right. */
function LightCard({ event }) {
  return (
    <>
      <img
        className="evcard-badge"
        src={event.logo || '/img/GOL_main_logo_pink.webp'}
        alt=""
        loading="lazy"
        width="110"
        height="110"
        style={event.logo ? { '--logo-scale': event.logo_scale ?? 1 } : undefined}
      />

      <div className="evcard-content">
        <h3 className="evcard-title">{event.name}</h3>
        <div className="evcard-meta">
          <div className="ev-date"><span className="ev-emoji">📅</span>{fmtDate(event.date)}</div>
          <div className="ev-place"><span className="ev-emoji">📍</span>{event.place}</div>
        </div>
        <div className="evcard-footer">
          <div className="evcard-foot-tags">
            <span className="evcard-pts"><span className="ev-emoji">🏆</span>+{event.points} pts</span>
            {event.category?.name && <span className="evcard-cat">{event.category.name}</span>}
            <span className={`u-label evcard-status${event.is_past ? ' done' : ''}`}>
              {event.is_past ? 'Proběhlo' : 'Akce'}
            </span>
          </div>
          <span className="evcard-detail">Detail →</span>
        </div>
      </div>
    </>
  );
}

/**
 * Unified event card.
 *
 * event : { id, slug, name, date, place, points, logo, is_past }
 * theme : 'dark' | 'light'   (default: 'dark')
 */
function EventCard({ event, theme = 'dark' }) {
  const handlePreload = useCallback(() => preloadEventDetail(event.slug), [event.slug]);
  return (
    <Link
      to={`/events/${event.slug}`}
      className={`evcard evcard-${theme}${theme === 'light' && event.is_past ? ' is-past' : ''}`}
      onMouseEnter={handlePreload}
      onFocus={handlePreload}
    >
      {theme === 'dark' ? <DarkCard event={event} /> : <LightCard event={event} />}
    </Link>
  );
}

export default memo(EventCard);

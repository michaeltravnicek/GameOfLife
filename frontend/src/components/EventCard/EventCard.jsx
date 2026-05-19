import { memo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fmtDate } from '../../utils/date';
import { preloadEventDetail } from '../../services/routePreload';
import DashedBorder from '../DashedBorder/DashedBorder';
import './EventCard.css';

function DarkCard({ event }) {
  return (
    <>
      <div className="evcard-dark-inner">
        <div className="evcard-title-wrap">
          <div className="evcard-brand">Game of Life</div>
          <div className="evcard-title">{event.name}</div>
        </div>
        <div className="evcard-meta">
          <div>📅 {fmtDate(event.date)}</div>
          <div>📍 {event.place}</div>
          <div>🏆 +{event.points} pts</div>
        </div>
      </div>

      <img
        className="evcard-badge"
        src={event.logo || '/logos/GOL_C50_transparent.png'}
        alt={event.name}
        loading="lazy"
        width="110"
        height="110"
      />
    </>
  );
}

function LightCard({ event }) {
  return (
    <>
      <DashedBorder />

      <span className={`evcard-status${event.is_past ? ' done' : ''}`}>
        {event.is_past ? 'Proběhlo' : 'Akce'}
      </span>

      <img
        className="evcard-badge"
        src={event.logo || '/logos/GOL_main_logo_pink.png'}
        alt=""
        loading="lazy"
        width="110"
        height="110"
      />

      <div className="evcard-content">
        <h3 className="evcard-title">{event.name}</h3>
        <div className="evcard-meta">
          <div>📅 {fmtDate(event.date)}</div>
          <div>📍 {event.place}</div>
        </div>
        <div className="evcard-footer">
          <span className="evcard-pts">+{event.points} pts</span>
          <span className="evcard-detail">Detail eventu →</span>
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
  // Warm up the detail chunk + this event's data on the first sign of intent.
  const handlePreload = useCallback(() => preloadEventDetail(event.slug), [event.slug]);
  return (
    <Link
      to={`/akce/${event.slug}`}
      className={`evcard evcard-${theme}${theme === 'light' && event.is_past ? ' is-past' : ''}`}
      onMouseEnter={handlePreload}
      onFocus={handlePreload}
    >
      {theme === 'dark'
        ? <DarkCard event={event} />
        : <LightCard event={event} />
      }
    </Link>
  );
}

// memo: cards re-render only when their `event` reference or `theme` actually
// changes. Critical for EventsPage where unrelated state (search input,
// filter chips, "Load more" appends) used to repaint every card.
export default memo(EventCard);

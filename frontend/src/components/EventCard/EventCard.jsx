import { useState } from 'react';
import { Link } from 'react-router-dom';
import { fmtDate } from '../../utils/date';
import './EventCard.css';

const DARK_W = 347;
const DARK_H = 166;

function DarkCard({ event, hovered }) {
  const borderColor = hovered ? '#E15463' : '#FFFFFF';
  return (
    <>
      <svg
        width={DARK_W}
        height={DARK_H}
        className="evcard-svg"
        style={{ top: 0, left: 0 }}
      >
        <rect
          x="1" y="1"
          width={DARK_W - 2}
          height={DARK_H - 2}
          rx="15" ry="15"
          fill="none"
          stroke={borderColor}
          strokeWidth="2"
          strokeDasharray="6 10"
          strokeLinecap="round"
          style={{ transition: 'stroke .2s ease' }}
        />
      </svg>

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
      />
    </>
  );
}

function LightCard({ event, hovered }) {
  const borderColor = hovered ? '#E15463' : '#1A1A1A';
  const detailColor = hovered ? '#E15463' : '#1A1A1A';
  const detailBorder = hovered ? '#E15463' : 'rgba(26,26,26,.45)';

  return (
    <>
      <div className="evcard-light-bg">
        <div className="evcard-light-bg-overlay" />
      </div>

      <svg
        width="100%"
        height={240}
        className="evcard-svg"
        style={{ top: 0, left: 0 }}
      >
        <rect
          x="1" y="1"
          width="calc(100% - 2px)"
          height={238}
          rx="13" ry="13"
          fill="none"
          stroke={borderColor}
          strokeWidth="2"
          strokeDasharray="6 10"
          strokeLinecap="round"
          style={{ transition: 'stroke .2s ease' }}
        />
      </svg>

      <span className="evcard-status">
        {event.is_past ? 'Proběhlo' : 'Akce'}
      </span>

      <img
        className="evcard-badge"
        src="/logos/GOL_main_logo_pink.png"
        alt=""
        loading="lazy"
      />

      <div className="evcard-content">
        <div className="evcard-title-wrap">
          <h3 className="evcard-title">{event.name}</h3>
        </div>
        <div className="evcard-meta">
          <div>📅 {fmtDate(event.date)}</div>
          <div>📍 {event.place}</div>
        </div>
        <div className="evcard-footer">
          <span className="evcard-pts">+{event.points} pts</span>
          <span
            className="evcard-detail"
            style={{ color: detailColor, borderBottom: `1px dashed ${detailBorder}` }}
          >
            Detail eventu →
          </span>
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
export default function EventCard({ event, theme = 'dark' }) {
  const [hovered, setHovered] = useState(false);

  return (
    <Link
      to={`/akce/${event.slug}`}
      className={`evcard evcard-${theme}${theme === 'light' && event.is_past ? ' is-past' : ''}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {theme === 'dark'
        ? <DarkCard event={event} hovered={hovered} />
        : <LightCard event={event} hovered={hovered} />
      }
    </Link>
  );
}

import { useCallback, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Button from '../Button/Button';
import { apiCheckin } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../Toast/ToastProvider';
import { invalidateQuery } from '../../services/queryCache';
import { extractApiError } from '../../services/errors';
import { getPosition, GEO_ERROR_MESSAGES } from '../../utils/geolocation';
import './CheckinBanner.css';

// Dismissals live in sessionStorage: hidden for the rest of the visit, back
// next session (check-ins are time-limited, so re-surfacing is desirable).
const DISMISSED_KEY = 'gol_checkin_dismissed';
const readDismissed = () => {
  try { return JSON.parse(sessionStorage.getItem(DISMISSED_KEY)) || []; } catch { return []; }
};

/**
 * Floating check-in notice over the home hero — an overlay, so it never
 * shifts the page layout. Shown when there's an event the user can check
 * into right now (event is happening + user hasn't yet claimed points).
 *
 * The "are you nearby?" check happens client-side via the Geolocation API
 * when the user taps "Potvrdit přítomnost". We don't request location until
 * then — no permission prompt on page load.
 *
 * Props:
 *   events: Array<{ slug, name, date, points, latitude, longitude, checkin_radius }>
 */
export default function CheckinBanner({ events = [] }) {
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  // Per-slug status. Each entry: 'idle' | 'locating' | 'submitting' | 'done' | 'error'
  const [statuses, setStatuses] = useState({});
  const [dismissed, setDismissed] = useState(readDismissed);

  const setStatus = useCallback((slug, status) => {
    setStatuses((prev) => ({ ...prev, [slug]: status }));
  }, []);

  const dismiss = useCallback((slug) => {
    setDismissed((prev) => {
      const next = [...prev, slug];
      try { sessionStorage.setItem(DISMISSED_KEY, JSON.stringify(next)); } catch { /* private mode */ }
      return next;
    });
  }, []);

  const handleCheckin = useCallback(async (event) => {
    if (!user) {
      navigate('/prihlasit', { state: { from: location.pathname } });
      return;
    }
    const { slug, name, points } = event;
    setStatus(slug, 'locating');

    let coords;
    try {
      coords = await getPosition();
    } catch (err) {
      toast.error(GEO_ERROR_MESSAGES[err.code] || 'Nelze zjistit polohu.', {
        title: 'Check-in selhal',
      });
      setStatus(slug, 'error');
      return;
    }

    setStatus(slug, 'submitting');
    try {
      const res = await apiCheckin(slug, coords.latitude, coords.longitude);
      if (res.already_had) {
        toast.info(`Body za "${name}" už máš.`, { title: 'Check-in OK' });
      } else {
        toast.success(`Připsáno +${res.points || points} bodů za "${name}"!`, {
          title: 'Check-in OK',
          duration: 6500,
        });
      }
      setStatus(slug, 'done');
      // Refresh the check-in list (this event drops off once its points are
      // claimed) + the leaderboard the new points feed into.
      invalidateQuery('checkin-events');
      invalidateQuery((k) => k.startsWith('leaderboard:'));
    } catch (err) {
      toast.error(extractApiError(err, 'Check-in se nepodařil.'), { title: 'Check-in selhal' });
      setStatus(slug, 'error');
    }
  }, [toast, setStatus, user, navigate, location.pathname]);

  const visible = events.filter((ev) => !dismissed.includes(ev.slug));
  if (!visible.length) return null;

  return (
    <div className="checkin-banners">
      {visible.map((ev) => {
        const st = statuses[ev.slug] || 'idle';
        const isBusy = st === 'locating' || st === 'submitting';
        const isDone = st === 'done';
        let btnLabel = user
          ? `Potvrdit přítomnost · +${ev.points} bodů`
          : `Přihlas se a získej +${ev.points} bodů`;
        if (st === 'locating') btnLabel = 'Zjišťuji polohu…';
        else if (st === 'submitting') btnLabel = 'Odesílám…';
        else if (st === 'done') btnLabel = '✓ Hotovo';
        else if (st === 'error') btnLabel = 'Zkusit znovu';

        return (
          <div key={ev.slug} className="checkin-banner" role="status">
            <div className="checkin-banner-icon" aria-hidden="true">📍</div>
            <div className="checkin-banner-text">
              <strong className="checkin-banner-title">{ev.name}</strong>
              <span>Právě probíhá! Check-in ti přinese <b>+{ev.points}&nbsp;bodů</b>.</span>
            </div>
            <Button
              variant="action"
              size="sm"
              onClick={() => handleCheckin(ev)}
              busy={isBusy}
              disabled={isBusy || isDone}
            >
              {btnLabel}
            </Button>
            <button
              type="button"
              className="checkin-banner-close"
              aria-label="Skrýt upozornění"
              onClick={() => dismiss(ev.slug)}
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}

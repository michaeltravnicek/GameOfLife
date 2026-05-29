import { useCallback, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiCheckin } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../Toast/ToastProvider';
import { invalidateQuery } from '../../services/queryCache';
import './CheckinBanner.css';

/**
 * Banner shown on the home page when there's an event the user can check
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

  const setStatus = useCallback((slug, status) => {
    setStatuses((prev) => ({ ...prev, [slug]: status }));
  }, []);

  const handleCheckin = useCallback((event) => {
    if (!user) {
      navigate('/prihlasit', { state: { from: location.pathname } });
      return;
    }
    const { slug, name, points } = event;
    if (!navigator.geolocation) {
      toast.error('Tvůj prohlížeč nepodporuje geolokaci.', { title: 'Check-in selhal' });
      return;
    }
    setStatus(slug, 'locating');

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setStatus(slug, 'submitting');
        try {
          const res = await apiCheckin(slug, pos.coords.latitude, pos.coords.longitude);
          if (res.already_had) {
            toast.info(`Body za "${name}" už máš.`, { title: 'Check-in OK' });
          } else {
            toast.success(`Připsáno +${res.points || points} bodů za "${name}"!`, {
              title: 'Check-in OK',
              duration: 6500,
            });
          }
          setStatus(slug, 'done');
          // Refresh home (banner list) + leaderboard.
          invalidateQuery('home');
          invalidateQuery((k) => k.startsWith('leaderboard:'));
        } catch (err) {
          const msg = err.response?.data?.error || 'Check-in se nepodařil.';
          toast.error(msg, { title: 'Check-in selhal' });
          setStatus(slug, 'error');
        }
      },
      (err) => {
        let msg = 'Nelze zjistit polohu.';
        if (err.code === 1) msg = 'Přístup k poloze zamítnut — povol ho v prohlížeči.';
        else if (err.code === 2) msg = 'Poloha není dostupná.';
        else if (err.code === 3) msg = 'Časový limit vypršel.';
        toast.error(msg, { title: 'Check-in selhal' });
        setStatus(slug, 'error');
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
    );
  }, [toast, setStatus, user, navigate, location.pathname]);

  if (!events.length) return null;

  return (
    <div className="checkin-banners">
      {events.map((ev) => {
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
          <div key={ev.slug} className="checkin-banner">
            <div className="checkin-banner-icon" aria-hidden="true">📍</div>
            <div className="checkin-banner-text">
              <strong>{ev.name}</strong>
              <span>Právě probíhá! Check-in ti přinese <strong>+{ev.points}&nbsp;bodů</strong>.</span>
            </div>
            <button
              type="button"
              className="checkin-banner-btn"
              onClick={() => handleCheckin(ev)}
              disabled={isBusy || isDone}
            >
              {btnLabel}
            </button>
          </div>
        );
      })}
    </div>
  );
}

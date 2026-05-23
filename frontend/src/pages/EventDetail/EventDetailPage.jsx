import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { fetchEventDetail, toggleRsvp } from '../../services/api';
import { useCachedQuery, invalidateQuery } from '../../services/queryCache';
import { reportError } from '../../services/errors';
import { CACHE_TTL } from '../../constants/config';
import { useAuth } from '../../context/AuthContext';
import Button from '../../components/Button/Button';
import SectionHeader from '../../components/SectionHeader/SectionHeader';
import { fmtDateShort, fmtTime, dayName } from '../../utils/date';
import './EventDetailPage.css';

// Lightbox is only needed once the user clicks on an image — pull it off the
// critical bundle and load it on demand.
const Lightbox = lazy(() => import('../../components/Lightbox/Lightbox'));

export default function EventDetailPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [lbOpen, setLbOpen] = useState(false);
  const [lbIndex, setLbIndex] = useState(0);

  const { data: event, error: queryError, refetch: refetchEvent } = useCachedQuery(
    `event:${slug}`,
    () => fetchEventDetail(slug),
    { enabled: !!slug, ttl: CACHE_TTL.EVENT_DETAIL },
  );
  const error = queryError
    ? (queryError.response?.status === 404 ? 'Akce nenalezena.' : 'Nepodařilo se načíst akci.')
    : '';

  const images = useMemo(() => {
    if (!event) return [];
    const list = [...(event.official_images || [])];
    (event.user_photos || []).forEach((p) => list.push(p.url));
    if (event.image) list.unshift(event.image);
    return list;
  }, [event]);

  const posterSrc = useMemo(() => {
    if (!event) return '/gallery/gal0.jpg';
    if (event.image) return event.image;
    if (event.official_images?.length) return event.official_images[0];
    return '/gallery/gal0.jpg';
  }, [event]);


  if (error) {
    return (
      <div className="event-detail-page">
        <main className="detail-main">
          <p style={{ textAlign: 'center', padding: '60px 20px' }}>{error}</p>
          <div style={{ textAlign: 'center' }}>
            <Link className="back-link" to="/akce">← Zpět na všechny akce</Link>
          </div>
        </main>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="event-detail-page">
        <p style={{ textAlign: 'center', padding: '120px 20px', color: '#fff' }}>Načítám…</p>
      </div>
    );
  }

  const handleRsvp = async () => {
    if (!user) {
      navigate('/prihlasit');
      return;
    }
    setBusy(true);
    try {
      await toggleRsvp(slug);
      // RSVP changed: refresh this event's cache + drop any events list pages
      // (rsvp_count on cards there may now be stale).
      invalidateQuery((k) => k.startsWith('events:'));
      await refetchEvent();
    } catch (err) {
      reportError('RSVP se nepodařilo. Zkus to prosím znovu.', err);
    } finally {
      setBusy(false);
    }
  };

  const openLb = (i) => { setLbIndex(i); setLbOpen(true); };
  const rules = event.rules ? event.rules.split(/\n+/).filter(Boolean) : [];
  const displayImages = images.slice(0, 4);
  const imgCount = Math.min(displayImages.length, 4);

  return (
    <div className="event-detail-page">

      {/* POSTER */}
      <section className="poster">
        <img className="poster-img" src={posterSrc} alt={event.name} fetchpriority="high" />
        <div className="poster-grain" />
        <div className="poster-vignette" />
        <div className="poster-top">
          <div className="badges">
            <span className={`ev-pill${!event.is_past ? ' live' : ''}`}>
              {event.is_past ? 'Proběhlo' : 'Nadcházející'}
            </span>
          </div>
          {event.logo
            ? <img className="poster-logo" src={event.logo} alt={event.name} />
            : <img className="poster-logo" src="/logos/GOL_main_logo_pink.png" alt={event.name} />}
        </div>
        <div className="credits">
          <span className="credits-rule" />
          <div className="credit">
            <div className="credit-label">— Datum —</div>
            <div className="credit-value">{fmtDateShort(event.date)}</div>
            <div className="credit-sub">{dayName(event.date)}</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Čas —</div>
            <div className="credit-value">{fmtTime(event.date)}</div>
            <div className="credit-sub">{event.name}</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Místo —</div>
            <div className="credit-value">{event.place}</div>
            <div className="credit-sub">&nbsp;</div>
          </div>
        </div>
      </section>

      {/* RSVP BAR */}
      <div className="rsvp-bar">
        <div className="rsvp-inner">
          {!event.is_past ? (
            <>
              <div className="rsvp-info">
                <span className="pts-tag">+{event.points} pts</span>
                {event.capacity != null && (
                  <span className="cap-tag">{event.rsvp_count} / {event.capacity} přihlášených</span>
                )}
              </div>
              <Button
                variant="cta"
                className={event.has_rsvp ? 'joined' : ''}
                onClick={handleRsvp}
                disabled={event.is_full && !event.has_rsvp}
                busy={busy}
              >
                {event.has_rsvp ? '✓ Jsi přihlášen/a' : event.is_full ? 'Plně obsazeno' : 'Přihlásit se ➤'}
              </Button>
            </>
          ) : (
            <div className="rsvp-recap">
              <span className="recap-eyebrow">— Proběhlo —</span>
              <span className="recap-text">{event.rsvp_count ?? 0} účastníků · +{event.points} pts</span>
            </div>
          )}
        </div>
      </div>

      {/* BODY */}
      <div className="body-wrap">
        <main className="detail-main">
          {event.description && (
            <section className="section">
              <SectionHeader eyebrow="— 01 · Popis —" heading={event.name} />
              <p className="desc-text">{event.description}</p>
            </section>
          )}

          {rules.length > 0 && (
            <section className="section">
              <SectionHeader eyebrow="— 02 · Pravidla —" heading="Hraje se férově." />
              <ol className="rules">
                {rules.map((r, i) => (
                  <li key={i}><span>{r}</span></li>
                ))}
              </ol>
            </section>
          )}

          {displayImages.length > 0 && (
            <section className="section">
              <SectionHeader eyebrow="— Galerie —" heading="Z této akce." />
              <div className="collage" data-count={imgCount}>
                {displayImages.map((src, i) => (
                  <figure key={i} onClick={() => openLb(i)}>
                    <img src={src} alt={`Galerie ${i + 1}`} loading="lazy" />
                  </figure>
                ))}
              </div>
            </section>
          )}
        </main>
      </div>

      {/* BACK STRIP */}
      <div className="back-strip">
        <div className="back-strip-inner">
          <Link className="back-link" to="/akce">← Zpět na všechny akce</Link>
          <Button
            variant="ghost"
            onClick={() => {
              const url = window.location.href;
              if (navigator.share) {
                // Intentional silent swallow: navigator.share throws
                // AbortError when the user dismisses the share sheet. That's
                // not an error from the user's POV, so don't toast it.
                navigator.share({ title: event.name, url }).catch(() => {});
              } else {
                navigator.clipboard?.writeText(url);
              }
            }}
          >
            Sdílet kámošům
          </Button>
        </div>
      </div>

      {lbOpen && (
        <Suspense fallback={null}>
          <Lightbox
            open={lbOpen}
            images={images}
            index={lbIndex}
            onClose={() => setLbOpen(false)}
            onPrev={() => setLbIndex((i) => (i - 1 + images.length) % images.length)}
            onNext={() => setLbIndex((i) => (i + 1) % images.length)}
          />
        </Suspense>
      )}
    </div>
  );
}

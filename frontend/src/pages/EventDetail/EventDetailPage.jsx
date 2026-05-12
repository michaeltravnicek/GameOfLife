import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { fetchEventDetail, toggleRsvp } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import './EventDetailPage.css';

const MONTHS = ['ledna', 'února', 'března', 'dubna', 'května', 'června', 'července', 'srpna', 'září', 'října', 'listopadu', 'prosince'];

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getDate()}. ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}
function formatDateShort(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getFullYear()).slice(2)}`;
}
function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}
function dayName(iso) {
  if (!iso) return '';
  const days = ['Neděle','Pondělí','Úterý','Středa','Čtvrtek','Pátek','Sobota'];
  return days[new Date(iso).getDay()];
}

export default function EventDetailPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [event, setEvent] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [lbOpen, setLbOpen] = useState(false);
  const [lbIndex, setLbIndex] = useState(0);

  useEffect(() => {
    setError('');
    fetchEventDetail(slug)
      .then(setEvent)
      .catch((e) => {
        if (e.response?.status === 404) setError('Akce nenalezena.');
        else setError('Nepodařilo se načíst akci.');
      });
  }, [slug]);

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

  useEffect(() => {
    if (!lbOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setLbOpen(false);
      if (e.key === 'ArrowLeft') setLbIndex((i) => (i - 1 + images.length) % images.length);
      if (e.key === 'ArrowRight') setLbIndex((i) => (i + 1) % images.length);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [lbOpen, images.length]);

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
      const res = await toggleRsvp(slug);
      setEvent((ev) => ({ ...ev, has_rsvp: res.rsvp, rsvp_count: res.rsvp_count }));
    } catch (err) {
      alert(err.response?.data?.error || 'Akce selhala.');
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
            <div className="credit-value">{formatDateShort(event.date)}</div>
            <div className="credit-sub">{dayName(event.date)}</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Čas —</div>
            <div className="credit-value">{formatTime(event.date)}</div>
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
              <button
                className={`btn-cta${event.has_rsvp ? ' joined' : ''}`}
                onClick={handleRsvp}
                disabled={busy || (event.is_full && !event.has_rsvp)}
              >
                {event.has_rsvp ? '✓ Jsi přihlášen/a' : event.is_full ? 'Plně obsazeno' : 'Přihlásit se ➤'}
              </button>
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
              <div className="sec-rule" />
              <div className="sec-eyebrow">— 01 · Popis —</div>
              <h2 className="sec-heading">{event.name}</h2>
              <p className="desc-text">{event.description}</p>
            </section>
          )}

          {rules.length > 0 && (
            <section className="section">
              <div className="sec-rule" />
              <div className="sec-eyebrow">— 02 · Pravidla —</div>
              <h2 className="sec-heading">Hraje se férově.</h2>
              <ol className="rules">
                {rules.map((r, i) => (
                  <li key={i}><span>{r}</span></li>
                ))}
              </ol>
            </section>
          )}

          {displayImages.length > 0 && (
            <section className="section">
              <div className="sec-rule" />
              <div className="sec-eyebrow">— Galerie —</div>
              <h2 className="sec-heading">Z této akce.</h2>
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
          <button
            className="btn-cta ghost"
            onClick={() => {
              if (navigator.share) navigator.share({ title: event.name, url: location.href });
              else navigator.clipboard.writeText(location.href);
            }}
          >
            Sdílet kámošům
          </button>
        </div>
      </div>

      {/* LIGHTBOX */}
      {lbOpen && images.length > 0 && (
        <div className="lightbox open" onClick={(e) => { if (e.target.classList.contains('lightbox')) setLbOpen(false); }}>
          <button className="lightbox-close" onClick={() => setLbOpen(false)}>×</button>
          <button className="lightbox-nav prev" onClick={() => setLbIndex((i) => (i - 1 + images.length) % images.length)}>‹</button>
          <img src={images[lbIndex]} alt="" />
          <button className="lightbox-nav next" onClick={() => setLbIndex((i) => (i + 1) % images.length)}>›</button>
        </div>
      )}
    </div>
  );
}

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
function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
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
        <div className="stage" /><div className="grain" />
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
        <div className="stage" /><div className="grain" />
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

  return (
    <div className="event-detail-page">
      <div className="stage" />
      <div className="grain" />

      <header className="hero">
        <div className="badges">
          <span className={`ev-pill${event.is_past ? '' : ' live'}`}>
            {event.is_past ? 'Proběhlo' : 'Nadcházející'}
          </span>
        </div>
        {event.logo
          ? <img className="hero-logo" src={event.logo} alt={event.name} />
          : <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(48px,8vw,96px)', textTransform: 'uppercase', textAlign: 'center', margin: '20px 0' }}>{event.name}</h1>}
        <div className="divider" />
      </header>

      <main className="detail-main">
        <div className="quick-grid">
          <div className="qcell"><div className="q-label">Datum</div><div className="q-value">{formatDate(event.date)}</div></div>
          <div className="qcell"><div className="q-label">Čas</div><div className="q-value">{formatTime(event.date)}</div></div>
          <div className="qcell"><div className="q-label">Místo</div><div className="q-value">{event.place}</div></div>
        </div>

        <div className="rsvp-strip">
          <div className="rsvp-info">
            <span className="pts-tag">+{event.points} pts</span>
            {event.capacity != null && (
              <span className="cap-tag">{event.rsvp_count} / {event.capacity} přihlášených</span>
            )}
          </div>
          <button
            className="btn-cta"
            style={event.has_rsvp ? { background: '#4a8a5e' } : undefined}
            onClick={handleRsvp}
            disabled={busy || (event.is_full && !event.has_rsvp)}
          >
            {event.has_rsvp ? '✓ Jsi přihlášen/a' : event.is_full ? 'Plná kapacita' : 'Přihlásit se ➤'}
          </button>
        </div>

        {event.description && (
          <section className="info-card">
            <h2 className="card-title">Popis</h2>
            <p className="desc-text">{event.description}</p>
          </section>
        )}

        {rules.length > 0 && (
          <section className="info-card">
            <h2 className="card-title">Pravidla</h2>
            <ol className="rules">
              {rules.map((r, i) => (
                <li key={i}><span className="num">{i + 1}</span><span>{r}</span></li>
              ))}
            </ol>
          </section>
        )}

        {images.length > 0 && (
          <section className="info-card">
            <h2 className="card-title">Galerie</h2>
            <div className="gal-grid">
              {images.map((src, i) => (
                <div key={i} className="gal-thumb" onClick={() => openLb(i)}>
                  <img src={src} alt={`Galerie ${i + 1}`} />
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="back-strip">
          <Link className="back-link" to="/akce">← Zpět na všechny akce</Link>
        </div>
      </main>

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

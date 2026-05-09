import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchGallery } from '../../services/api';
import './GalleryPage.css';

const CZ_MONTHS = ['Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen', 'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec'];

function monthKey(iso) {
  if (!iso) return 'unknown';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
function monthLabel(key) {
  if (key === 'unknown') return 'Neurčeno';
  const [y, m] = key.split('-');
  return `${CZ_MONTHS[Number(m) - 1]} ${y}`;
}

export default function GalleryPage() {
  const [view, setView] = useState('slideshow');
  const [photos, setPhotos] = useState([]);
  const [cur, setCur] = useState(0);
  const [activeMonth, setActiveMonth] = useState('all');
  const [lbOpen, setLbOpen] = useState(false);
  const [lbPhotos, setLbPhotos] = useState([]);
  const [lbIndex, setLbIndex] = useState(0);

  const tx = useRef(0);

  useEffect(() => {
    fetchGallery().then((d) => setPhotos(d.photos || [])).catch(() => {});
  }, []);

  const months = useMemo(() => {
    const set = new Set(photos.map((p) => monthKey(p.event_date)));
    return Array.from(set);
  }, [photos]);

  const n = photos.length;
  const goSlide = (idx) => setCur(((idx % Math.max(n, 1)) + Math.max(n, 1)) % Math.max(n, 1));

  const openLb = (list, i) => {
    setLbPhotos(list);
    setLbIndex(i);
    setLbOpen(true);
  };
  const lbStep = (d) => setLbIndex((i) => (i + d + lbPhotos.length) % lbPhotos.length);

  useEffect(() => {
    if (!lbOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setLbOpen(false);
      if (e.key === 'ArrowLeft') lbStep(-1);
      if (e.key === 'ArrowRight') lbStep(1);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [lbOpen, lbPhotos.length]);

  const visibleMonths = activeMonth === 'all' ? months : [activeMonth];

  const slidePhoto = photos[cur] || {};
  const prevPhoto = photos[(cur - 1 + n) % n] || {};
  const nextPhoto = photos[(cur + 1) % n] || {};

  const onTouchStart = (e) => { tx.current = e.touches[0].clientX; };
  const onTouchEnd = (e) => {
    const dx = e.changedTouches[0].clientX - tx.current;
    if (Math.abs(dx) > 40) goSlide(dx < 0 ? cur + 1 : cur - 1);
  };

  return (
    <div className="gallery-page">
      <div className="bg-texture" />

      <div className="hero">
        <div className="eyebrow">Game of Life</div>
        <h1>Galerie</h1>
        <p className="tagline">Vzpomínky, zážitky a okamžiky, které stojí za to si připomenout.</p>
        <div className="divider" />
      </div>

      <div className="view-toggle">
        <button className={`vt-btn${view === 'slideshow' ? ' on' : ''}`} onClick={() => setView('slideshow')}>
          <span className="vt-icon">▶</span> Slideshow
        </button>
        <button className={`vt-btn${view === 'calendar' ? ' on' : ''}`} onClick={() => setView('calendar')}>
          <span className="vt-icon">▦</span> Kalendář
        </button>
      </div>

      {n === 0 && (
        <p style={{ textAlign: 'center', padding: '60px 20px', color: 'rgba(255,241,212,.6)' }}>
          V galerii zatím nejsou žádné fotografie.
        </p>
      )}

      {view === 'slideshow' && n > 0 && (
        <div id="view-slideshow">
          <div className="counter"><span>{cur + 1}</span> / <span>{n}</span></div>
          <div className="gal-container">
            <div
              className="gal-side"
              style={{ background: `url('${prevPhoto.url}') center/cover no-repeat` }}
              onClick={() => goSlide(cur - 1)}
            />
            <div
              className="gal-main"
              style={{ background: `url('${slidePhoto.url}') center/cover no-repeat` }}
              onClick={(e) => { if (!e.target.closest('.gal-zone')) openLb(photos, cur); }}
              onTouchStart={onTouchStart}
              onTouchEnd={onTouchEnd}
            >
              <div className="gal-zone gal-zone-left" onClick={() => goSlide(cur - 1)}>
                <div className="gal-zone-arrow">‹</div>
              </div>
              <div className="gal-zone gal-zone-right" onClick={() => goSlide(cur + 1)}>
                <div className="gal-zone-arrow">›</div>
              </div>
              <div className="gal-caption">
                <div className="gal-caption-label">{slidePhoto.is_user_photo ? `Foto: ${slidePhoto.uploaded_by}` : 'Akce'}</div>
                <div className="gal-caption-title">{slidePhoto.event_name}</div>
              </div>
            </div>
            <div
              className="gal-side"
              style={{ background: `url('${nextPhoto.url}') center/cover no-repeat` }}
              onClick={() => goSlide(cur + 1)}
            />
          </div>
          <div className="gal-dots">
            {photos.map((_, i) => (
              <div
                key={i}
                className={`gal-dot${i === cur ? ' on' : ''}`}
                onClick={() => goSlide(i)}
              />
            ))}
          </div>
        </div>
      )}

      {view === 'calendar' && n > 0 && (
        <div id="view-calendar" style={{ display: 'block' }}>
          <div className="month-filters">
            <button className={`mf-chip${activeMonth === 'all' ? ' on' : ''}`} onClick={() => setActiveMonth('all')}>Vše</button>
            {months.map((m) => (
              <button
                key={m}
                className={`mf-chip${activeMonth === m ? ' on' : ''}`}
                onClick={() => setActiveMonth(m)}
              >
                {monthLabel(m)}
              </button>
            ))}
          </div>
          {visibleMonths.map((m) => {
            const monthPhotos = photos.filter((p) => monthKey(p.event_date) === m);
            return (
              <div key={m} className="month-section">
                <div className="month-heading">{monthLabel(m)}</div>
                <div className="month-count">
                  {monthPhotos.length} {monthPhotos.length === 1 ? 'fotografie' : 'fotografií'}
                </div>
                <div className="photo-grid">
                  {monthPhotos.map((p, i) => (
                    <div key={i} className="photo-item" onClick={() => openLb(monthPhotos, i)}>
                      <img src={p.url} alt={p.event_name} loading="lazy" />
                      <div className="photo-item-caption">
                        <div className="photo-item-label">{p.is_user_photo ? 'Komunita' : 'Akce'}</div>
                        <div className="photo-item-title">{p.event_name}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="gallery-footer">
        <Link to="/akce" className="btn-pill">Zobrazit nadcházející akce ➤</Link>
      </div>

      {lbOpen && lbPhotos.length > 0 && (
        <div className="lightbox open" onClick={(e) => { if (e.target.classList.contains('lightbox')) setLbOpen(false); }}>
          <button className="lb-close" onClick={() => setLbOpen(false)}>×</button>
          <button className="lb-nav prev" onClick={() => lbStep(-1)}>‹</button>
          <img src={lbPhotos[lbIndex].url} alt="" />
          <button className="lb-nav next" onClick={() => lbStep(1)}>›</button>
          <div className="lb-info">
            {lbPhotos[lbIndex].event_name}{lbPhotos[lbIndex].is_user_photo && ` · foto: ${lbPhotos[lbIndex].uploaded_by}`}
          </div>
        </div>
      )}
    </div>
  );
}

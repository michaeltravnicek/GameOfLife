import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchGallery } from '../../services/api';
import { usePaginatedQuery } from '../../services/usePaginatedQuery';
import { CACHE_TTL, GALLERY_PREFETCH_TAIL, PAGE_SIZE_GALLERY } from '../../constants/config';
import { monthKey, monthLabel } from '../../utils/date';
import './GalleryPage.css';

// Lightbox loaded only when user opens a fullscreen photo.
const Lightbox = lazy(() => import('../../components/Lightbox/Lightbox'));

const PAGE_SIZE = PAGE_SIZE_GALLERY;
const PREFETCH_TAIL = GALLERY_PREFETCH_TAIL;

const extractPhotos = (r) => r.photos || [];
const extractHasMore = (r) => !!r.has_more;
const extractCount = (r) => r.count ?? 0;

export default function GalleryPage() {
  const [view, setView] = useState('slideshow');
  const [cur, setCur] = useState(0);
  const [activeMonth, setActiveMonth] = useState('all');
  const [lbOpen, setLbOpen] = useState(false);
  const [lbPhotos, setLbPhotos] = useState([]);
  const [lbIndex, setLbIndex] = useState(0);

  const tx = useRef(0);
  const viewToggleRef = useRef(null);
  const [vtInd, setVtInd] = useState({ left: 5, width: 0, visible: false });

  useLayoutEffect(() => {
    const group = viewToggleRef.current;
    if (!group) return undefined;
    const measure = () => {
      const activeBtn = group.querySelector('.vt-btn.on');
      if (!activeBtn) { setVtInd((s) => ({ ...s, visible: false })); return; }
      const g = group.getBoundingClientRect();
      const a = activeBtn.getBoundingClientRect();
      setVtInd({ left: a.left - g.left, width: a.width, visible: true });
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [view]);

  const {
    items: photos, hasMore, totalCount, loading, loadingMore, loadMore,
  } = usePaginatedQuery({
    cacheKey: 'gallery:first',
    fetcher: (offset, limit) => fetchGallery({ limit, offset }),
    pageSize: PAGE_SIZE,
    ttl: CACHE_TTL.GALLERY,
    errorMessage: 'Nepodařilo se načíst další fotografie.',
    extractItems: extractPhotos,
    extractHasMore,
    extractCount,
  });

  // If the loaded photo set shrinks (cache invalidation, filter), keep `cur`
  // in bounds so we don't index undefined and blank the slideshow.
  useEffect(() => {
    setCur((c) => {
      if (photos.length === 0) return 0;
      return c >= photos.length ? photos.length - 1 : c;
    });
  }, [photos.length]);

  // Auto-prefetch next page when the slideshow cursor approaches the loaded tail.
  useEffect(() => {
    if (view !== 'slideshow') return;
    if (!hasMore || loadingMore) return;
    if (photos.length === 0) return;
    if (cur >= photos.length - PREFETCH_TAIL) {
      loadMore();
    }
  }, [cur, photos.length, view, hasMore, loadingMore, loadMore]);

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

  const visibleMonths = activeMonth === 'all' ? months : [activeMonth];

  const slidePhoto = photos[cur] || {};
  const prevPhoto = photos[(cur - 1 + n) % n] || {};
  const nextPhoto = photos[(cur + 1) % n] || {};

  const onTouchStart = (e) => { tx.current = e.touches[0].clientX; };
  const onTouchEnd = (e) => {
    const dx = e.changedTouches[0].clientX - tx.current;
    if (Math.abs(dx) > 40) goSlide(dx < 0 ? cur + 1 : cur - 1);
  };

  const loadedCounter = hasMore
    ? `${n} / ${totalCount}`
    : `${n}`;

  return (
    <div className="gallery-page">
      <div className="bg-texture" />

      <div className="hero">
        <div className="eyebrow">Game of Life</div>
        <h1>Galerie</h1>
        <p className="tagline">Vzpomínky, zážitky a okamžiky, které stojí za to si připomenout.</p>
        <div className="divider" />
      </div>

      <div
        ref={viewToggleRef}
        className={`view-toggle${vtInd.visible ? ' has-active' : ''}`}
        style={{ '--pill-left': `${vtInd.left}px`, '--pill-w': `${vtInd.width}px` }}
      >
        <button className={`vt-btn${view === 'slideshow' ? ' on' : ''}`} onClick={() => setView('slideshow')}>
          <span className="vt-icon">▶</span> Slideshow
        </button>
        <button className={`vt-btn${view === 'calendar' ? ' on' : ''}`} onClick={() => setView('calendar')}>
          <span className="vt-icon">▦</span> Kalendář
        </button>
      </div>

      {loading && (
        <p style={{ textAlign: 'center', padding: '60px 20px', color: 'rgba(255,241,212,.6)' }}>
          Načítám galerii…
        </p>
      )}

      {!loading && n === 0 && (
        <p style={{ textAlign: 'center', padding: '60px 20px', color: 'rgba(255,241,212,.6)' }}>
          V galerii zatím nejsou žádné fotografie.
        </p>
      )}

      {view === 'slideshow' && n > 0 && (
        <div id="view-slideshow">
          <div className="counter"><span>{cur + 1}</span> / <span>{loadedCounter}</span></div>
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
              <div
                className="gal-zone gal-zone-left"
                role="button"
                tabIndex={0}
                aria-label="Předchozí fotografie"
                onClick={() => goSlide(cur - 1)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goSlide(cur - 1); } }}
              >
                <div className="gal-zone-arrow" aria-hidden="true">‹</div>
              </div>
              <div
                className="gal-zone gal-zone-right"
                role="button"
                tabIndex={0}
                aria-label="Další fotografie"
                onClick={() => goSlide(cur + 1)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goSlide(cur + 1); } }}
              >
                <div className="gal-zone-arrow" aria-hidden="true">›</div>
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
          <div className="gal-dots" role="tablist" aria-label="Přepnout na konkrétní fotografii">
            {photos.map((_, i) => (
              <div
                key={i}
                role="tab"
                tabIndex={0}
                aria-label={`Snímek ${i + 1} z ${photos.length}`}
                aria-selected={i === cur}
                className={`gal-dot${i === cur ? ' on' : ''}`}
                onClick={() => goSlide(i)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goSlide(i); } }}
              />
            ))}
          </div>
        </div>
      )}

      {view === 'calendar' && n > 0 && (
        <div id="view-calendar">
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

          {hasMore && (
            <div className="load-more-row">
              <button
                type="button"
                className="mf-chip"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? 'Načítám…' : `Načíst další (${totalCount - n})`}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="gallery-footer">
        <Link to="/akce" className="btn-pill">Zobrazit nadcházející akce ➤</Link>
      </div>

      {lbOpen && (
        <Suspense fallback={null}>
          <Lightbox
            open={lbOpen}
            photos={lbPhotos}
            index={lbIndex}
            showInfo
            onClose={() => setLbOpen(false)}
            onPrev={() => lbStep(-1)}
            onNext={() => lbStep(1)}
          />
        </Suspense>
      )}
    </div>
  );
}

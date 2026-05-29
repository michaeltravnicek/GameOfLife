import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { fetchEvents, fetchGallery, fetchSeasons, uploadGalleryPhoto } from '../../services/api';
import { usePaginatedQuery } from '../../services/usePaginatedQuery';
import { prefetchQuery, invalidateQuery, useCachedQuery } from '../../services/queryCache';
import { useAuth } from '../../context/AuthContext';
import { reportError } from '../../services/errors';
import { CACHE_TTL, GALLERY_PREFETCH_TAIL, PAGE_SIZE_GALLERY } from '../../constants/config';
import PageHero from '../../components/PageHero/PageHero';
import Reveal from '../../components/Reveal/Reveal';
import Button from '../../components/Button/Button';
import Modal from '../../components/Modal/Modal';
import { fmtDateShort } from '../../utils/date';
import './GalleryPage.css';

// Lightbox loaded only when user opens a fullscreen photo.
const Lightbox = lazy(() => import('../../components/Lightbox/Lightbox'));

const PAGE_SIZE = PAGE_SIZE_GALLERY;
const PREFETCH_TAIL = GALLERY_PREFETCH_TAIL;

const extractPhotos = (r) => r.photos || [];
const extractHasMore = (r) => !!r.has_more;
const extractCount = (r) => r.count ?? 0;

export default function GalleryPage() {
  const { canUpload } = useAuth();
  const [view, setView] = useState('slideshow');
  const [cur, setCur] = useState(0);
  const [activeSeason, setActiveSeason] = useState('all'); // 'all', a season id (string), or 'unknown'
  const [lbOpen, setLbOpen] = useState(false);
  const [lbPhotos, setLbPhotos] = useState([]);
  const [lbIndex, setLbIndex] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadPreview, setUploadPreview] = useState(null);
  const [uploadEvent, setUploadEvent] = useState('');
  const [uploadCaption, setUploadCaption] = useState('');

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

  // Past events only — newest first — for the upload modal's event picker.
  // Fetched only once the modal is opened.
  const { data: pastEventsData } = useCachedQuery(
    'gallery-upload-past-events',
    () => fetchEvents({ period: 'past', limit: 200 }),
    { ttl: CACHE_TTL.EVENTS, enabled: uploadOpen },
  );
  const pastEvents = pastEventsData?.events || [];

  const resetUploadModal = () => {
    setUploadFile(null);
    setUploadPreview(null);
    setUploadEvent('');
    setUploadCaption('');
  };

  const handleUploadFile = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploadFile(file);
    const reader = new FileReader();
    reader.onload = () => setUploadPreview(reader.result);
    reader.readAsDataURL(file);
  };

  const handleUploadCancel = () => {
    if (uploading) return;
    setUploadOpen(false);
    resetUploadModal();
  };

  const handleUploadSubmit = async () => {
    if (!uploadFile) return;
    setUploading(true);
    try {
      await uploadGalleryPhoto({
        image: uploadFile,
        event: uploadEvent,
        caption: uploadCaption.trim(),
      });
      invalidateQuery('gallery:first');
      await prefetchQuery('gallery:first', () => fetchGallery({ limit: PAGE_SIZE, offset: 0 }));
      setUploadOpen(false);
      resetUploadModal();
    } catch (err) {
      reportError('Nahrání fotky se nepodařilo.', err);
    } finally {
      setUploading(false);
    }
  };

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

  // Seasons drive the calendar grouping (replaces the old per-month buckets).
  // Newest season first so the most recent photos lead.
  const { data: seasonsData } = useCachedQuery('seasons', fetchSeasons, { ttl: CACHE_TTL.LEADERBOARD });
  const seasons = useMemo(
    () => [...(seasonsData?.seasons || [])].sort((a, b) => (a.start < b.start ? 1 : -1)),
    [seasonsData],
  );

  // Which season a photo's event falls into. Dates are 'YYYY-MM-DD', so a
  // lexicographic compare on the date portion is correct. 'unknown' = no match
  // (e.g. a photo whose event predates every configured season).
  const seasonOf = useCallback((iso) => {
    if (!iso) return 'unknown';
    const d = String(iso).slice(0, 10);
    const hit = seasons.find((s) => s.start <= d && d <= s.end);
    return hit ? String(hit.id) : 'unknown';
  }, [seasons]);

  const seasonLabel = useCallback((key) => {
    if (key === 'unknown') return 'Neurčeno';
    return seasons.find((s) => String(s.id) === key)?.name || 'Sezóna';
  }, [seasons]);

  // Season buckets (newest-first) that actually contain photos, plus a trailing
  // 'unknown' bucket when some photos don't map to any season.
  const seasonKeys = useMemo(() => {
    const present = new Set(photos.map((p) => seasonOf(p.event_date)));
    const ordered = seasons.map((s) => String(s.id)).filter((id) => present.has(id));
    if (present.has('unknown')) ordered.push('unknown');
    return ordered;
  }, [photos, seasons, seasonOf]);

  const n = photos.length;
  const goSlide = (idx) => setCur(((idx % Math.max(n, 1)) + Math.max(n, 1)) % Math.max(n, 1));

  const openLb = (list, i) => {
    setLbPhotos(list);
    setLbIndex(i);
    setLbOpen(true);
  };
  const lbStep = (d) => setLbIndex((i) => (i + d + lbPhotos.length) % lbPhotos.length);

  const visibleSeasons = activeSeason === 'all' ? seasonKeys : [activeSeason];

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

      <PageHero
        eyebrow="Game of Life"
        title="Galerie"
        tagline="Vzpomínky, zážitky a okamžiky, které stojí za to si připomenout."
      />

      {canUpload && (
        <div className="gal-upload">
          <button type="button" className="gal-upload-btn" onClick={() => setUploadOpen(true)}>
            + Nahrát fotku do galerie
          </button>
        </div>
      )}

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
          <div className="season-filters">
            <button className={`sf-chip${activeSeason === 'all' ? ' on' : ''}`} onClick={() => setActiveSeason('all')}>Vše</button>
            {seasonKeys.map((key) => (
              <button
                key={key}
                className={`sf-chip${activeSeason === key ? ' on' : ''}`}
                onClick={() => setActiveSeason(key)}
              >
                {seasonLabel(key)}
              </button>
            ))}
          </div>
          {visibleSeasons.map((key) => {
            const seasonPhotos = photos.filter((p) => seasonOf(p.event_date) === key);
            return (
              <div key={key} className="season-section">
                <div className="season-heading">{seasonLabel(key)}</div>
                <div className="season-count">
                  {seasonPhotos.length} {seasonPhotos.length === 1 ? 'fotografie' : 'fotografií'}
                </div>
                <Reveal stagger className="photo-grid">
                  {seasonPhotos.map((p, i) => (
                    <div key={i} className="photo-item" onClick={() => openLb(seasonPhotos, i)}>
                      <img src={p.url} alt={p.event_name} loading="lazy" />
                      <div className="photo-item-caption">
                        <div className="photo-item-label">{p.is_user_photo ? 'Komunita' : 'Akce'}</div>
                        <div className="photo-item-title">{p.event_name}</div>
                      </div>
                    </div>
                  ))}
                </Reveal>
              </div>
            );
          })}

          {hasMore && (
            <div className="load-more-row">
              <button
                type="button"
                className="sf-chip"
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
        <Button as="link" to="/akce" size="lg">Zobrazit nadcházející akce <span className="arr" /></Button>
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

      <Modal open={uploadOpen} onClose={uploading ? undefined : handleUploadCancel} labelledBy="gal-upload-title">
        <div className="gal-upload-eyebrow">— Nová fotka —</div>
        <h3 id="gal-upload-title" className="gal-upload-title">
          Sdílej <span className="pink">moment.</span>
        </h3>

        <label className="gal-upload-drop">
          {uploadPreview ? (
            <img src={uploadPreview} alt="Náhled" className="gal-upload-preview" />
          ) : (
            <span className="gal-upload-drop-text">Klikni a vyber obrázek</span>
          )}
          <input type="file" accept="image/*" hidden onChange={handleUploadFile} disabled={uploading} />
        </label>

        <div className="gal-upload-field">
          <label htmlFor="gal-event-select" className="gal-upload-label">Z jaké akce?</label>
          <select
            id="gal-event-select"
            className="gal-upload-select"
            value={uploadEvent}
            onChange={(e) => setUploadEvent(e.target.value)}
            disabled={uploading}
          >
            <option value="">— Bez akce —</option>
            {pastEvents.map((ev) => (
              <option key={ev.slug} value={ev.slug}>
                {fmtDateShort(ev.date)} · {ev.name}
              </option>
            ))}
          </select>
        </div>

        <div className="gal-upload-field">
          <label htmlFor="gal-caption" className="gal-upload-label">Popisek <span className="gal-upload-hint">nepovinné</span></label>
          <input
            id="gal-caption"
            type="text"
            className="gal-upload-input"
            value={uploadCaption}
            onChange={(e) => setUploadCaption(e.target.value)}
            maxLength={255}
            placeholder="Něco krátkého…"
            disabled={uploading}
          />
        </div>

        <div className="gal-upload-buttons">
          <Button variant="nav" onClick={handleUploadCancel} disabled={uploading}>Zrušit</Button>
          <Button variant="nav" onClick={handleUploadSubmit} busy={uploading} disabled={!uploadFile || uploading}>
            {uploading ? 'Nahrávám…' : 'Nahrát'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import { fetchEvents, fetchGallery, fetchSeasons, uploadGalleryPhoto } from '../../services/api';
import { usePaginatedQuery } from '../../services/usePaginatedQuery';
import { prefetchQuery, invalidateQuery, useCachedQuery } from '../../services/queryCache';
import { useAuth } from '../../context/AuthContext';
import { reportError } from '../../services/errors';
import { CACHE_TTL, PAGE_SIZE_GALLERY } from '../../constants/config';
import PageHero from '../../components/PageHero/PageHero';
import LazyImg from '../../components/LazyImg/LazyImg';
import Reveal from '../../components/Reveal/Reveal';
import PillTabs from '../../components/PillTabs/PillTabs';
import Button from '../../components/Button/Button';
import Modal from '../../components/Modal/Modal';
import { fmtDateShort, monthLabel } from '../../utils/date';
import './GalleryPage.css';

// Lightbox loaded only when user opens a fullscreen photo.
const Lightbox = lazy(() => import('../../components/Lightbox/Lightbox'));

const PAGE_SIZE = PAGE_SIZE_GALLERY;

const extractPhotos = (r) => r.photos || [];
const extractHasMore = (r) => !!r.has_more;
const extractCount = (r) => r.count ?? 0;

export default function GalleryPage() {
  const { canUpload } = useAuth();
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

  // Season filter as leaderboard-style pill toggles: "Vše" + one per season.
  const seasonTabs = useMemo(
    () => [{ key: 'all', label: 'Vše' }, ...seasonKeys.map((key) => ({ key, label: seasonLabel(key) }))],
    [seasonKeys, seasonLabel],
  );

  // ── Calendar grouping: filter by season chip, then bucket by YYYY-MM and
  // sort month-buckets newest-first (see `monthLabel` in utils/date). Photos
  // without a usable event_date land in a trailing 'unknown' bucket.
  const monthGroups = useMemo(() => {
    const filtered = activeSeason === 'all'
      ? photos
      : photos.filter((p) => seasonOf(p.event_date) === activeSeason);
    const buckets = new Map();
    filtered.forEach((p) => {
      const iso = String(p.event_date || '').slice(0, 10);
      const key = /^\d{4}-\d{2}/.test(iso) ? iso.slice(0, 7) : 'unknown';
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(p);
    });
    // Newest month first; 'unknown' always last.
    const keys = [...buckets.keys()].sort((a, b) => {
      if (a === 'unknown') return 1;
      if (b === 'unknown') return -1;
      return a < b ? 1 : -1;
    });
    return keys.map((key) => ({ key, photos: buckets.get(key) }));
  }, [photos, activeSeason, seasonOf]);

  const n = photos.length;

  const openLb = (list, i) => {
    setLbPhotos(list);
    setLbIndex(i);
    setLbOpen(true);
  };
  const lbStep = (d) => setLbIndex((i) => (i + d + lbPhotos.length) % lbPhotos.length);

  return (
    <div className="gallery-page">
      <div className="bg-texture" />

      <PageHero
        className="gallery-hero"
        eyebrow={<><span className="gal-eyebrow-lead">Vzpomínky, </span>zážitky a okamžiky</>}
        title="Galerie"
      />

      {canUpload && (
        <div className="gal-upload">
          <button type="button" className="gal-upload-btn" onClick={() => setUploadOpen(true)}>
            + Nahrát fotku do galerie
          </button>
        </div>
      )}

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

      {n > 0 && (
        <div id="view-calendar">
          <div className="season-filters">
            <PillTabs tabs={seasonTabs} active={activeSeason} onChange={setActiveSeason} />
          </div>
          {monthGroups.map(({ key, photos: monthPhotos }) => (
            <div key={key} className="season-section">
              <div className="season-heading">{monthLabel(key)}</div>
              <div className="season-count">
                {monthPhotos.length} {monthPhotos.length === 1 ? 'fotografie' : 'fotografií'}
              </div>
              <Reveal stagger className="photo-grid">
                {monthPhotos.map((p, i) => (
                  <div key={i} className="photo-item" onClick={() => openLb(monthPhotos, i)}>
                    {/* Grid tiles are ~330px wide — the 768px variant is enough
                        on every viewport; the lightbox opens the original.
                        LazyImg fetches only on-screen tiles + ~one row ahead. */}
                    <LazyImg src={p.url_mobile || p.url} alt={p.event_name} />
                    <div className="photo-item-caption">
                      <div className="photo-item-label">{p.is_user_photo ? 'Komunita' : 'Akce'}</div>
                      <div className="photo-item-title">{p.event_name}</div>
                    </div>
                  </div>
                ))}
              </Reveal>
            </div>
          ))}

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
        <Button as="link" to="/events" size="lg">Zobrazit nadcházející akce <span className="arr" /></Button>
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
          <Button variant="frost" onClick={handleUploadCancel} disabled={uploading}>Zrušit</Button>
          <Button variant="action" onClick={handleUploadSubmit} busy={uploading} disabled={!uploadFile || uploading}>
            {uploading ? 'Nahrávám…' : 'Nahrát'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

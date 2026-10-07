import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchEvents, fetchGallery, fetchGalleryMonths, fetchLikedPhotos, fetchSeasons, setPhotoLike,
  uploadGalleryPhoto,
} from '../../services/api';
import { refetchQuery, setQueryData, useCachedQuery } from '../../services/queryCache';
import { queryKeys } from '../../services/queryKeys';
import { useAuth } from '../../context/AuthContext';
import { reportError } from '../../services/errors';
import { CACHE_TTL, PAGE_SIZE_GALLERY } from '../../constants/config';
import PageHero from '../../components/PageHero/PageHero';
import PageStage from '../../components/PageStage/PageStage';
import PageState from '../../components/PageState/PageState';
import PillTabs from '../../components/PillTabs/PillTabs';
import Button from '../../components/Button/Button';
import Modal from '../../components/Modal/Modal';
import { fmtDateShort } from '../../utils/date';
import { useImagePreview } from '../../hooks/useImagePreview';
import GalleryMonth from './GalleryMonth';
import '../../styles/edit-form.css';
import './GalleryPage.css';

// Lightbox loaded only when user opens a fullscreen photo.
const Lightbox = lazy(() => import('../../components/Lightbox/Lightbox'));

const EMPTY_OVERRIDES = {};
const NO_MONTHS = [];

// 'YYYY-MM' of an event date, in the server's time zone like the API's months.
const monthOf = (iso) => (/^\d{4}-\d{2}/.test(iso || '') ? iso.slice(0, 7) : 'unknown');

export default function GalleryPage() {
  const { canUpload, user } = useAuth();
  const navigate = useNavigate();
  // Like state the user has changed since the page loaded, keyed by photo id.
  // The photo lists themselves are owned by each month's usePaginatedQuery
  // cache, so overriding here is what lets a tap paint instantly without
  // invalidating a month (and re-fetching its photos) on every heart. Tagged
  // with the user it belongs to: after a logout on this page the hearts must
  // not stay lit.
  const owner = user?.username ?? null;
  const [likeState, setLikeState] = useState({ owner, byId: {} });
  const likeOverrides = likeState.owner === owner ? likeState.byId : EMPTY_OVERRIDES;
  const setLikeOverride = useCallback((id, value) => {
    setLikeState((prev) => ({
      owner,
      byId: { ...(prev.owner === owner ? prev.byId : {}), [id]: value },
    }));
  }, [owner]);
  const [activeSeason, setActiveSeason] = useState('all'); // 'all', a season id (string), or 'unknown'
  const [lbOpen, setLbOpen] = useState(false);
  const [lbPhotos, setLbPhotos] = useState([]);
  const [lbIndex, setLbIndex] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  // 15 MB matches the server's upload limit (IMAGE_MAX_UPLOAD_MB).
  const upload = useImagePreview({ maxSizeMB: 15 });
  const [uploadEvent, setUploadEvent] = useState('');
  const [uploadCaption, setUploadCaption] = useState('');

  // Just the month headings and their counts. Each GalleryMonth fetches its
  // own photos, a page at a time, once it scrolls near.
  const {
    data: monthsData, loading, error, refetch: retry,
  } = useCachedQuery(queryKeys.galleryMonths, fetchGalleryMonths, { ttl: CACHE_TTL.GALLERY });
  const months = monthsData?.months || NO_MONTHS;

  // Past events only — newest first — for the upload modal's event picker.
  // Fetched only once the modal is opened.
  const { data: pastEventsData } = useCachedQuery(
    queryKeys.galleryUploadEvents,
    () => fetchEvents({ period: 'past', limit: 200 }),
    { ttl: CACHE_TTL.EVENTS, enabled: uploadOpen },
  );
  const pastEvents = pastEventsData?.events || [];

  const resetUploadModal = () => {
    upload.clear();
    setUploadEvent('');
    setUploadCaption('');
  };

  const handleUploadFile = (e) => {
    upload.onSelect(e);
    // Cleared so picking the same file again still fires onChange.
    e.target.value = '';
  };

  const handleUploadCancel = () => {
    if (uploading) return;
    setUploadOpen(false);
    resetUploadModal();
  };

  const handleUploadSubmit = async () => {
    if (!upload.file) return;
    setUploading(true);
    try {
      await uploadGalleryPhoto({
        image: upload.file,
        event: uploadEvent,
        caption: uploadCaption.trim(),
      });
      // In place, so the grid keeps showing while the new photo lands: the
      // headings, and the month the photo went into.
      const month = monthOf(pastEvents.find((ev) => ev.slug === uploadEvent)?.date);
      await Promise.all([
        refetchQuery(queryKeys.galleryMonths, fetchGalleryMonths),
        refetchQuery(
          queryKeys.galleryMonth(month),
          () => fetchGallery({ month, limit: PAGE_SIZE_GALLERY, offset: 0 }),
        ),
      ]);
      setUploadOpen(false);
      resetUploadModal();
    } catch (err) {
      reportError('Nahrání fotky se nepodařilo.', err);
    } finally {
      setUploading(false);
    }
  };

  // Which photos this user has liked. A separate request because /gallery/ is
  // edge-cached and must stay identical for everyone — see fetchLikedPhotos.
  // Anonymous visitors never ask (enabled: false); clearCache() on logout drops
  // this entry, so the hearts empty the moment someone signs out.
  const { data: likedData } = useCachedQuery(queryKeys.likedPhotos, fetchLikedPhotos, {
    enabled: !!user,
    ttl: CACHE_TTL.GALLERY,
  });
  const likedIds = useMemo(() => new Set(likedData?.liked || []), [likedData]);

  // A photo as it should render right now: the cached public row, plus this
  // user's like state, plus any local override from a tap this session. Order
  // matters — the override is the freshest of the three and must win.
  const withLikes = useCallback(
    (p) => {
      const base = likedIds.has(p.id) ? { ...p, liked_by_me: true } : p;
      return likeOverrides[p.id] ? { ...base, ...likeOverrides[p.id] } : base;
    },
    [likeOverrides, likedIds],
  );

  const toggleLike = useCallback(async (photo) => {
    // Official event photos have no id — PhotoLike hangs off UserPhoto only.
    if (photo.id == null) return;
    if (!user) {
      navigate('/prihlasit', { state: { from: '/galerie' } });
      return;
    }
    // `photo` is already through withLikes at both call sites, so its
    // liked_by_me reflects the fetched list; the override still wins.
    const current = likeOverrides[photo.id] ?? photo;
    const next = !current.liked_by_me;
    // Paint first: a heart that waits for the network feels broken.
    setLikeOverride(photo.id, {
      liked_by_me: next,
      like_count: Math.max(0, (current.like_count ?? 0) + (next ? 1 : -1)),
    });
    try {
      // PUT/DELETE are idempotent, so a double-tap settles on the real state
      // rather than inverting it.
      const data = await setPhotoLike(photo.id, next);
      setLikeOverride(photo.id, { liked_by_me: data.liked, like_count: data.count });
      // Fold it into the cached like list too. `likeOverrides` is component
      // state and dies on unmount, so without this a like would un-paint itself
      // as soon as you left the gallery and came back inside the TTL.
      setQueryData(queryKeys.likedPhotos, (prev) => (prev ? {
        ...prev,
        liked: data.liked
          ? [...new Set([...(prev.liked || []), photo.id])]
          : (prev.liked || []).filter((id) => id !== photo.id),
      } : prev));
    } catch (err) {
      // Roll back to whatever we knew before the tap. Coerced: liked_by_me is
      // absent from the gallery payload for an unliked photo, and
      // aria-pressed={undefined} drops the attribute.
      setLikeOverride(photo.id, {
        liked_by_me: !!current.liked_by_me, like_count: current.like_count,
      });
      reportError('Lajk se nepodařilo uložit.', err);
    }
  }, [likeOverrides, navigate, setLikeOverride, user]);

  // Seasons drive the calendar grouping, newest first so recent photos lead.
  const { data: seasonsData } = useCachedQuery(queryKeys.seasons, fetchSeasons, { ttl: CACHE_TTL.LEADERBOARD });
  const seasons = useMemo(
    () => [...(seasonsData?.seasons || [])].sort((a, b) => (a.start < b.start ? 1 : -1)),
    [seasonsData],
  );

  // The seasons a month belongs to: every season whose window touches it.
  // Months are compared as 'YYYY-MM' strings, so a month a season boundary
  // splits counts towards both. 'unknown' = no season (undated photos, or a
  // month between seasons).
  const seasonsOf = useCallback((month) => {
    if (month === 'unknown') return ['unknown'];
    const hits = seasons
      .filter((s) => s.start.slice(0, 7) <= month && month <= s.end.slice(0, 7))
      .map((s) => String(s.id));
    return hits.length ? hits : ['unknown'];
  }, [seasons]);

  const seasonLabel = useCallback((key) => {
    if (key === 'unknown') return 'Neurčeno';
    return seasons.find((s) => String(s.id) === key)?.name || 'Sezóna';
  }, [seasons]);

  // Season buckets (newest-first) that actually contain photos, plus a trailing
  // 'unknown' bucket when some months don't map to any season.
  const seasonKeys = useMemo(() => {
    const present = new Set(months.flatMap((m) => seasonsOf(m.month)));
    const ordered = seasons.map((s) => String(s.id)).filter((id) => present.has(id));
    if (present.has('unknown')) ordered.push('unknown');
    return ordered;
  }, [months, seasons, seasonsOf]);

  // Season filter as leaderboard-style pill toggles: "Vše" + one per season.
  const seasonTabs = useMemo(
    () => [{ key: 'all', label: 'Vše' }, ...seasonKeys.map((key) => ({ key, label: seasonLabel(key) }))],
    [seasonKeys, seasonLabel],
  );

  // Months arrive newest-first with 'unknown' last; the season chip only
  // narrows them.
  const visibleMonths = useMemo(
    () => (activeSeason === 'all'
      ? months
      : months.filter((m) => seasonsOf(m.month).includes(activeSeason))),
    [months, activeSeason, seasonsOf],
  );

  const n = months.length;

  // A failed first page must not read as "the gallery is empty".
  const [retrying, setRetrying] = useState(false);
  const handleRetry = useCallback(() => {
    setRetrying(true);
    Promise.resolve(retry()).catch(() => {}).finally(() => setRetrying(false));
  }, [retry]);

  const openLb = (list, i) => {
    setLbPhotos(list);
    setLbIndex(i);
    setLbOpen(true);
  };
  const lbStep = (d) => setLbIndex((i) => (i + d + lbPhotos.length) % lbPhotos.length);

  return (
    <div className="gallery-page has-stage">
      <PageStage image="gal11" position="center 30%" tint="calm" />

      <PageHero
        className="gallery-hero"
        eyebrow={<><span className="gal-eyebrow-lead">Vzpomínky, </span>zážitky a okamžiky</>}
        title="Galerie"
      />

      {canUpload && (
        <div className="gal-upload">
          <Button variant="pill" onClick={() => setUploadOpen(true)}>
            + Nahrát fotku do galerie
          </Button>
        </div>
      )}

      {loading && n === 0 && <PageState kind="loading" text="Načítám galerii…" />}

      {!loading && error && n === 0 && (
        <PageState
          kind="error"
          text="Galerii se nepodařilo načíst. Zkontroluj připojení a zkus to znovu."
          onRetry={handleRetry}
          busy={retrying}
        />
      )}

      {!loading && !error && n === 0 && (
        <PageState kind="empty" text="V galerii zatím nejsou žádné fotografie." />
      )}

      {n > 0 && (
        <div id="view-calendar">
          <div className="season-filters">
            <PillTabs tabs={seasonTabs} active={activeSeason} onChange={setActiveSeason} />
          </div>
          {visibleMonths.map(({ month, count }) => (
            <GalleryMonth
              key={month}
              month={month}
              count={count}
              withLikes={withLikes}
              onToggleLike={toggleLike}
              onOpen={openLb}
            />
          ))}
        </div>
      )}

      <div className="gallery-footer">
        <Button as="link" to="/events" size="lg">Zobrazit nadcházející akce <span className="arr" /></Button>
      </div>

      {lbOpen && (
        <Suspense fallback={null}>
          <Lightbox
            open={lbOpen}
            // Same override merge as the grid, so a heart tapped in the
            // lightbox stays lit when you step to the next photo and back.
            photos={lbPhotos.map(withLikes)}
            index={lbIndex}
            showInfo
            onToggleLike={toggleLike}
            onClose={() => setLbOpen(false)}
            onPrev={() => lbStep(-1)}
            onNext={() => lbStep(1)}
          />
        </Suspense>
      )}

      <Modal open={uploadOpen} onClose={uploading ? undefined : handleUploadCancel} labelledBy="gal-upload-title">
        <div className="gol-modal-eyebrow">Nová fotka</div>
        <h3 id="gal-upload-title" className="gol-modal-title gal-upload-title">
          Sdílej <span className="pink">moment.</span>
        </h3>

        <label className="gal-upload-drop">
          {upload.preview ? (
            <img src={upload.preview} alt="Náhled" className="gal-upload-preview" />
          ) : (
            <span className="gal-upload-drop-text">Klikni a vyber obrázek</span>
          )}
          <input type="file" accept="image/*" hidden onChange={handleUploadFile} disabled={uploading} />
        </label>

        <div className="gal-upload-field">
          <label htmlFor="gal-event-select" className="gal-upload-label">Z jaké akce?</label>
          <select
            id="gal-event-select"
            className="gol-input gal-upload-select"
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
            className="gol-input"
            value={uploadCaption}
            onChange={(e) => setUploadCaption(e.target.value)}
            maxLength={255}
            placeholder="Něco krátkého…"
            disabled={uploading}
          />
        </div>

        <div className="gol-modal-buttons">
          <Button variant="frost" onClick={handleUploadCancel} disabled={uploading}>Zrušit</Button>
          <Button variant="action" onClick={handleUploadSubmit} busy={uploading} disabled={!upload.file || uploading}>
            {uploading ? 'Nahrávám…' : 'Nahrát'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

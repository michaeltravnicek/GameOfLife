import { useCallback, useState } from 'react';
import { fetchGallery } from '../../services/api';
import { usePaginatedQuery } from '../../services/usePaginatedQuery';
import { queryKeys } from '../../services/queryKeys';
import { useNearViewport } from '../../hooks/useNearViewport';
import { CACHE_TTL, PAGE_SIZE_GALLERY } from '../../constants/config';
import PageState from '../../components/PageState/PageState';
import LoadMore from '../../components/LoadMore/LoadMore';
import LazyImg from '../../components/LazyImg/LazyImg';
import Reveal from '../../components/Reveal/Reveal';
import { monthLabel } from '../../utils/date';
import { pressable } from '../../utils/a11y';
import { plural } from '../../utils/plural';

const extractPhotos = (r) => r.photos || [];
const extractHasMore = (r) => !!r.has_more;
const extractCount = (r) => r.count ?? 0;

/**
 * One month of the gallery: its heading, its first PAGE_SIZE_GALLERY photos and
 * a "Načíst další" for the rest.
 *
 * Nothing is fetched until the section comes near the viewport. Until then
 * empty tiles hold the space the first page will take, so the months further
 * down stay out of range instead of all counting as "near" at once.
 *
 * month : 'YYYY-MM' or 'unknown'
 * count : photos in the month, from /gallery/months/
 * withLikes, onToggleLike : the page's like overlay (see GalleryPage)
 * onOpen(photos, index)   : open the lightbox on this month's loaded photos
 */
export default function GalleryMonth({ month, count, withLikes, onToggleLike, onOpen }) {
  const [ref, near] = useNearViewport('600px');
  const fetcher = useCallback(
    (offset, limit) => fetchGallery({ month, offset, limit }),
    [month],
  );
  const {
    items: photos, hasMore, totalCount, loadingMore, loadMore, error, retry,
  } = usePaginatedQuery({
    cacheKey: queryKeys.galleryMonth(month),
    fetcher,
    pageSize: PAGE_SIZE_GALLERY,
    ttl: CACHE_TTL.GALLERY,
    errorMessage: 'Nepodařilo se načíst další fotografie.',
    extractItems: extractPhotos,
    extractHasMore,
    extractCount,
    enabled: near,
  });

  const [retrying, setRetrying] = useState(false);
  const handleRetry = useCallback(() => {
    setRetrying(true);
    Promise.resolve(retry()).catch(() => {}).finally(() => setRetrying(false));
  }, [retry]);

  const placeholders = photos.length === 0 && !error ? Math.min(count, PAGE_SIZE_GALLERY) : 0;

  return (
    <section ref={ref} className="season-section">
      <div className="season-heading">{monthLabel(month)}</div>
      <div className="season-count">
        {count} {plural(count, 'fotografie', 'fotografie', 'fotografií')}
      </div>

      {error && photos.length === 0 ? (
        <PageState
          kind="error"
          compact
          text="Fotky z tohoto měsíce se nepodařilo načíst."
          onRetry={handleRetry}
          busy={retrying}
        />
      ) : (
        <Reveal stagger className="photo-grid">
          {Array.from({ length: placeholders }, (_, i) => (
            <div key={`slot-${i}`} className="photo-item is-placeholder" aria-hidden="true" />
          ))}
          {photos.map((raw, i) => {
            const p = withLikes(raw);
            return (
              <div key={i} className="photo-item" {...pressable(() => onOpen(photos, i))}>
                {/* Grid tiles are ~330px wide — the 768px variant is enough
                    on every viewport; the lightbox opens the original.
                    LazyImg fetches only on-screen tiles + ~one row ahead. */}
                <LazyImg src={p.url_mobile || p.url} alt={p.event_name} />
                {p.id != null && (
                  <button
                    type="button"
                    className={`photo-like${p.liked_by_me ? ' is-liked' : ''}`}
                    aria-pressed={!!p.liked_by_me}
                    aria-label={p.liked_by_me ? 'Zrušit lajk' : 'Líbí se mi'}
                    // The tile itself opens the lightbox; without this the
                    // heart would do both.
                    onClick={(e) => { e.stopPropagation(); onToggleLike(p); }}
                  >
                    <span className="photo-like-ico" aria-hidden="true">♥</span>
                    {p.like_count > 0 && (
                      <span className="photo-like-n">{p.like_count}</span>
                    )}
                  </button>
                )}
                <div className="photo-item-caption">
                  <div className="photo-item-label">{p.is_user_photo ? 'Komunita' : 'Akce'}</div>
                  <div className="photo-item-title">{p.event_name}</div>
                </div>
              </div>
            );
          })}
        </Reveal>
      )}

      {hasMore && (
        <LoadMore onClick={loadMore} busy={loadingMore} remaining={totalCount - photos.length} />
      )}
    </section>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './Lightbox.css';

// Keep in sync with --lb-slide-dur in Lightbox.css — how long the outgoing
// image layer stays mounted so its slide-out keyframe can finish.
const LB_SLIDE_MS = 420;

/**
 * Full-screen image lightbox rendered via React portal.
 *
 * Two usage modes:
 *
 * Simple (string URLs):
 *   images={['/media/a.jpg', '/media/b.jpg']}
 *
 * Rich (Gallery objects with metadata):
 *   photos={[{ url, event_name, is_user_photo, uploaded_by }]}
 *   showInfo={true}   — shows caption bar
 *
 * Keyboard: Escape closes, ArrowLeft/Right navigates.
 * Clicking the backdrop closes; navigating slides the photo directionally.
 */
export default function Lightbox({
  open,
  images,
  photos,
  index = 0,
  onClose,
  onNext,
  onPrev,
  showInfo = false,
}) {
  const list = photos || images || [];
  const total = list.length;
  const srcAt = (i) => {
    const it = list[i];
    return it ? (typeof it === 'string' ? it : it.url) : null;
  };
  const current = list[index] || null;
  const imgSrc = srcAt(index);

  // Restore focus to whatever element the user activated to open the lightbox.
  // Without this, closing the lightbox drops focus on document.body and the
  // keyboard user loses their place in the page.
  const previousFocusRef = useRef(null);

  // Directional slide state: the image currently sliding out (`out`), which way
  // we're moving, and an `id` that bumps every step. The id is folded into the
  // incoming <img>'s key so it remounts and replays its keyframe each time.
  const [motion, setMotion] = useState({ out: null, dir: null, id: 0 });
  const motionIdRef = useRef(0);
  const prevIndexRef = useRef(index);
  // Set by the nav handlers so a wrap (last→first) still reads as "next".
  const pendingDirRef = useRef(null);

  const goNext = useCallback(() => { pendingDirRef.current = 'next'; onNext?.(); }, [onNext]);
  const goPrev = useCallback(() => { pendingDirRef.current = 'prev'; onPrev?.(); }, [onPrev]);

  // When the index prop changes, kick off a slide in the pending direction
  // (falling back to index comparison for anything that changes it directly).
  useEffect(() => {
    if (index === prevIndexRef.current) return undefined;
    const out = prevIndexRef.current;
    const dir = pendingDirRef.current || (index > out ? 'next' : 'prev');
    const id = ++motionIdRef.current;
    setMotion({ out, dir, id });
    prevIndexRef.current = index;
    pendingDirRef.current = null;
    const t = setTimeout(() => {
      setMotion((m) => (m.id === id ? { ...m, out: null } : m));
    }, LB_SLIDE_MS);
    return () => clearTimeout(t);
  }, [index]);

  useEffect(() => {
    if (!open) return undefined;
    previousFocusRef.current = document.activeElement;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft') goPrev();
      if (e.key === 'ArrowRight') goNext();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      const prev = previousFocusRef.current;
      if (prev && typeof prev.focus === 'function') prev.focus();
    };
  }, [open, onClose, goNext, goPrev]);

  if (!open || !imgSrc) return null;

  const meta = showInfo && current && typeof current === 'object' ? current : null;
  const photographer = meta?.is_user_photo && meta?.uploaded_by ? meta.uploaded_by : null;
  const altText = [meta?.event_name, photographer ? `foto: ${photographer}` : null].filter(Boolean).join(' · ');

  // No direction yet (first open) → the incoming image gets the zoom-in open
  // animation; during navigation it slides in from the side instead.
  const enterClass = motion.dir ? `enter-${motion.dir}` : 'is-open';

  return createPortal(
    <div
      className="lb-overlay"
      // Clicking the dark backdrop (overlay or the empty stage around the photo)
      // closes; clicking the photo itself does not.
      onClick={(e) => {
        if (e.target.classList.contains('lb-overlay') || e.target.classList.contains('lb-stage')) onClose();
      }}
    >
      <button className="lb-close" onClick={onClose} aria-label="Zavřít">×</button>

      {total > 1 && (
        <>
          <button className="lb-nav-btn lb-nav-prev" onClick={goPrev} aria-label="Předchozí">‹</button>
          <button className="lb-nav-btn lb-nav-next" onClick={goNext} aria-label="Další">›</button>
        </>
      )}

      <div className="lb-stage">
        {/* Outgoing photo — kept mounted just long enough to slide off-screen. */}
        {motion.out != null && motion.out !== index && (
          <img key={`out-${motion.id}`} className={`lb-img leave-${motion.dir}`} src={srcAt(motion.out)} alt="" />
        )}
        {/* Incoming photo — keyed by index+id so it remounts and replays the
            slide/zoom keyframe on every step. */}
        <img key={`in-${index}-${motion.id}`} className={`lb-img ${enterClass}`} src={imgSrc} alt={altText} />
      </div>

      {meta && (meta.event_name || photographer) && (
        <div className="lb-info">
          {meta.event_name && <div className="u-label lb-info-title">{meta.event_name}</div>}
          {photographer && (
            <div className="lb-info-credit">
              <span className="lb-info-cam" aria-hidden="true">📷</span>
              <span className="u-label lb-info-credit-label">Foto:</span>
              <span className="lb-info-credit-name">{photographer}</span>
            </div>
          )}
        </div>
      )}
    </div>,
    document.body,
  );
}

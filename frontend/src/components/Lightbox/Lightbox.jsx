import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import './Lightbox.css';

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
 * Clicking backdrop closes.
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
  const current = list[index] || null;
  const imgSrc = current ? (typeof current === 'string' ? current : current.url) : null;

  // Restore focus to whatever element the user activated to open the lightbox.
  // Without this, closing the lightbox drops focus on document.body and the
  // keyboard user loses their place in the page.
  const previousFocusRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    previousFocusRef.current = document.activeElement;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft') onPrev();
      if (e.key === 'ArrowRight') onNext();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      const prev = previousFocusRef.current;
      if (prev && typeof prev.focus === 'function') prev.focus();
    };
  }, [open, onClose, onNext, onPrev]);

  if (!open || !imgSrc) return null;

  const caption = showInfo && current && typeof current === 'object'
    ? [
        current.event_name,
        current.is_user_photo && current.uploaded_by ? `foto: ${current.uploaded_by}` : null,
      ].filter(Boolean).join(' · ')
    : null;

  return createPortal(
    <div
      className="lb-overlay"
      onClick={(e) => { if (e.target.classList.contains('lb-overlay')) onClose(); }}
    >
      <button className="lb-close" onClick={onClose} aria-label="Zavřít">×</button>

      {total > 1 && (
        <>
          <button className="lb-nav-btn lb-nav-prev" onClick={onPrev} aria-label="Předchozí">‹</button>
          <button className="lb-nav-btn lb-nav-next" onClick={onNext} aria-label="Další">›</button>
        </>
      )}

      <img src={imgSrc} alt={caption || ''} />

      {caption && <div className="lb-info">{caption}</div>}
    </div>,
    document.body,
  );
}

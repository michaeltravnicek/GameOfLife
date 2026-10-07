import { useEffect, useRef } from 'react';
import DashedBorder from '../DashedBorder/DashedBorder';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import './Modal.css';

/**
 * Dashed-bordered overlay modal.
 *
 * Click outside is intentionally NOT a close — every caller has explicit
 * action buttons inside, so accidental dismissal isn't desirable.
 * Escape closes via `onClose` if provided.
 */
export default function Modal({ open, onClose, children, labelledBy, width }) {
  const cardRef = useRef(null);

  useEffect(() => {
    if (!open || !onClose) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useFocusTrap(cardRef, open);

  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
      <div ref={cardRef} tabIndex={-1} className="modal-card" style={width ? { maxWidth: `${width}px` } : undefined}>
        <DashedBorder
          baseColor="var(--alpha-cream-20)"
          dashColor="var(--alpha-cream-85)"
          radius={12}
          width={1.5}
          dash={6}
          gap={8}
        />
        <div className="modal-inner">
          {children}
        </div>
      </div>
    </div>
  );
}

import { useEffect, useRef } from 'react';
import DashedBorder from '../DashedBorder/DashedBorder';
import './Modal.css';

const FOCUSABLE = 'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

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

  // Trap focus inside the modal: move focus in on open, keep Tab cycling within.
  useEffect(() => {
    if (!open) return undefined;
    const card = cardRef.current;
    const previouslyFocused = document.activeElement;
    const focusables = () => Array.from(card?.querySelectorAll(FOCUSABLE) || []);
    (focusables()[0] || card)?.focus();

    const onKey = (e) => {
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (items.length === 0) { e.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    card?.addEventListener('keydown', onKey);
    return () => {
      card?.removeEventListener('keydown', onKey);
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [open]);

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
          baseColor="rgba(255,241,212,0.18)"
          dashColor="rgba(255,241,212,0.85)"
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

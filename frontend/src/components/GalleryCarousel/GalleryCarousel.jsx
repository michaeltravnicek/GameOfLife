import {
  useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import './GalleryCarousel.css';

/**
 * Sliding gallery carousel.
 *
 * Each image is one persistent DOM node whose *relative* position to the current
 * index (-2 … 2) drives a CSS `data-pos`. When the index changes, every node's
 * position shifts by one and CSS transitions slide them across — the centre image
 * physically glides into the right slot while the next preview eases into centre,
 * instead of the old instant background swap.
 *
 * The only seam in an infinite carousel is when a node wraps from one edge to the
 * other; we detect that jump and snap it (transition disabled for one frame) while
 * it's invisible (opacity 0), so the wrap is never seen.
 */
const relativePos = (i, current, n) => {
  let rel = ((i - current) % n + n) % n; // 0 … n-1
  if (rel > n / 2) rel -= n; // fold into roughly (-n/2, n/2]
  return rel;
};

export default function GalleryCarousel({ images }) {
  const n = images.length;
  const [current, setCurrent] = useState(0);
  const prevRel = useRef(new Map());
  const [snap, setSnap] = useState(() => new Set());

  const prev = useCallback(() => setCurrent((c) => (c - 1 + n) % n), [n]);
  const next = useCallback(() => setCurrent((c) => (c + 1) % n), [n]);

  const slides = useMemo(
    () => images.map((url, i) => ({ url, i, rel: n ? relativePos(i, current, n) : 0 })),
    [images, current, n],
  );

  // Disable the transition for any node that wrapped across the stage this step.
  useEffect(() => {
    const toSnap = new Set();
    slides.forEach(({ i, rel }) => {
      const p = prevRel.current.get(i);
      if (p !== undefined && Math.abs(rel - p) > 1) toSnap.add(i);
      prevRel.current.set(i, rel);
    });
    if (!toSnap.size) return undefined;
    setSnap(toSnap);
    // Re-enable transitions on the next frame, after the snap has painted.
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => setSnap(new Set())));
    return () => cancelAnimationFrame(raf);
  }, [slides]);

  const onStageKey = useCallback((e) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
  }, [prev, next]);

  if (!n) return null;

  return (
    <div
      className="gc-stage"
      role="group"
      aria-roledescription="kolotoč"
      aria-label="Galerie"
      tabIndex={0}
      onKeyDown={onStageKey}
    >
      {slides.map(({ url, i, rel }) => {
        const pos = Math.max(-2, Math.min(2, rel));
        const interactive = pos === -1 || pos === 1;
        return (
          <div
            key={i}
            className={`gc-slide${snap.has(i) ? ' gc-snap' : ''}`}
            data-pos={pos}
            aria-hidden={pos !== 0}
            style={{ backgroundImage: `url('${url}')` }}
            role={interactive ? 'button' : undefined}
            tabIndex={interactive ? 0 : undefined}
            aria-label={interactive ? (pos === -1 ? 'Předchozí fotka' : 'Další fotka') : undefined}
            onClick={interactive ? (pos === -1 ? prev : next) : undefined}
            onKeyDown={interactive ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); (pos === -1 ? prev : next)(); }
            } : undefined}
          />
        );
      })}
    </div>
  );
}

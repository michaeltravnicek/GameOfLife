import { useCallback, useRef, useState } from 'react';
import './LazyImg.css';

/**
 * Image that only starts downloading when it scrolls near the viewport.
 *
 * Unlike native loading="lazy" (Chrome may prefetch several thousand px
 * ahead), this uses an IntersectionObserver with a small margin, so only the
 * tiles on screen plus roughly one row ahead are fetched. One-shot: once the
 * src is set it stays loaded (the browser cache keeps it anyway).
 *
 * Until the real image arrives a same-slot placeholder holds the layout
 * (default 4:3 — masonry columns settle to the true ratio once loaded).
 */
export default function LazyImg({ src, alt = '', className = '', margin = '400px', ratio = '4 / 3' }) {
  const [near, setNear] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const ioRef = useRef(null);

  const ref = useCallback((el) => {
    if (ioRef.current) {
      ioRef.current.disconnect();
      ioRef.current = null;
    }
    if (!el || near) return;
    // No IO support → just load; worst case equals the old behaviour.
    if (typeof IntersectionObserver === 'undefined') {
      setNear(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setNear(true);
          io.disconnect();
          ioRef.current = null;
        }
      },
      { rootMargin: `${margin} 0px` },
    );
    io.observe(el);
    ioRef.current = io;
  }, [near, margin]);

  return (
    <span ref={ref} className={`lazyimg${loaded ? ' is-loaded' : ''} ${className}`} style={!loaded ? { aspectRatio: ratio } : undefined}>
      {near && <img src={src} alt={alt} onLoad={() => setLoaded(true)} />}
    </span>
  );
}

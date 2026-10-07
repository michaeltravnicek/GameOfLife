import { useCallback, useRef, useState } from 'react';

/**
 * One-shot "is this about to scroll into view". Returns `[ref, near]`: `near`
 * flips to true the first time the element comes within `margin` of the
 * viewport (above or below) and stays true.
 *
 * Unlike useReveal there is no timeout fallback: this gates network requests,
 * and forcing it true after a delay would fetch everything off-screen too.
 * Without IntersectionObserver it is true straight away.
 */
export function useNearViewport(margin = '400px') {
  const [near, setNear] = useState(false);
  const ioRef = useRef(null);

  const ref = useCallback((el) => {
    if (ioRef.current) {
      ioRef.current.disconnect();
      ioRef.current = null;
    }
    if (!el || near) return;
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

  return [ref, near];
}

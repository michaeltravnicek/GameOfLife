import { useCallback, useRef, useState } from 'react';

/**
 * One-shot scroll reveal. Returns `[ref, inView]`: attach `ref` to an element,
 * and `inView` flips to true (and stays true) the first time it scrolls into
 * view. Pair with the `.reveal` / `.reveal-stagger` classes in reveal.css.
 *
 * `ref` is a CALLBACK ref on purpose. The elements we reveal are often rendered
 * conditionally (e.g. an events grid that only appears once data has loaded), so
 * the node attaches AFTER mount. A plain `useRef` + `useEffect` would read
 * `ref.current === null` on the first (empty) render and never re-run when the
 * node finally appears — leaving the content stuck at `opacity:0` ("nothing
 * shows up"). A callback ref runs every time React attaches/detaches the node,
 * so the observer is always wired to the real element.
 *
 * Falls back to visible when IntersectionObserver is unavailable so content is
 * never stuck hidden.
 */
export function useReveal({ threshold = 0.15, rootMargin = '0px 0px -8% 0px' } = {}) {
  const [inView, setInView] = useState(false);
  const observerRef = useRef(null);
  const revealedRef = useRef(false);

  const ref = useCallback((el) => {
    // Detach from any previous node (element unmounted or was replaced).
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    // Nothing to observe, or already revealed (one-shot — stays visible).
    if (!el || revealedRef.current) return;

    if (typeof IntersectionObserver === 'undefined') {
      revealedRef.current = true;
      setInView(true);
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          revealedRef.current = true;
          setInView(true);
          io.disconnect();
          observerRef.current = null;
        }
      },
      { threshold, rootMargin },
    );
    io.observe(el);
    observerRef.current = io;
  }, [threshold, rootMargin]);

  return [ref, inView];
}

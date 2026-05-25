import { useEffect, useRef, useState } from 'react';

/**
 * One-shot scroll reveal. Returns `[ref, inView]`: attach `ref` to an element,
 * and `inView` flips to true (and stays true) the first time it scrolls into
 * view. Pair with the `.reveal` / `.reveal-stagger` classes in reveal.css.
 *
 * Falls back to visible when IntersectionObserver is unavailable so content is
 * never stuck hidden.
 */
export function useReveal({ threshold = 0.15, rootMargin = '0px 0px -8% 0px' } = {}) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (inView) return undefined;
    const el = ref.current;
    if (!el) return undefined;
    if (typeof IntersectionObserver === 'undefined') {
      setInView(true);
      return undefined;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold, rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold, rootMargin, inView]);

  return [ref, inView];
}

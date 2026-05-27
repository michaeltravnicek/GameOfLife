import { useCallback, useRef, useState } from 'react';

/**
 * One-shot scroll reveal. Returns `[ref, inView]`: attach `ref` to an element,
 * and `inView` flips to true (and stays true) the first time it scrolls into
 * view. Pair with the `.reveal` / `.reveal-stagger` classes in reveal.css.
 *
 * Uses a callback ref so the observer always attaches to the real DOM node even
 * when the element renders conditionally (e.g. a grid that only appears once
 * data has loaded).
 *
 * Safety fallback: if IntersectionObserver never fires within 1.5 s (slow
 * cold-start, hidden parent, browser quirk), the content is forced visible so
 * it never stays stuck at opacity:0.
 */
export function useReveal({ threshold = 0.15, rootMargin = '0px 0px -8% 0px' } = {}) {
  const [inView, setInView] = useState(false);
  const observerRef = useRef(null);
  const timerRef = useRef(null);
  const revealedRef = useRef(false);

  const doReveal = useCallback(() => {
    if (revealedRef.current) return;
    revealedRef.current = true;
    setInView(true);
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const ref = useCallback((el) => {
    // Tear down observer + fallback timer when element unmounts or is replaced.
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    // Nothing to observe, or already revealed (one-shot — stays visible).
    if (!el || revealedRef.current) return;

    if (typeof IntersectionObserver === 'undefined') {
      doReveal();
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) doReveal();
      },
      { threshold, rootMargin },
    );
    io.observe(el);
    observerRef.current = io;

    // If IO never fires (content at viewport edge, hidden parent, browser quirk),
    // force the reveal so items are never permanently stuck invisible.
    timerRef.current = setTimeout(doReveal, 1500);
  }, [threshold, rootMargin, doReveal]);

  return [ref, inView];
}

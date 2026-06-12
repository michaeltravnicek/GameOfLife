import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Animated count-up. Returns `[ref, value]`: attach `ref` to the element that
 * shows the number; the first time it scrolls into view, `value` tweens from 0
 * to `target` (eased, ~1.3 s) and then holds.
 *
 * `target` may be a number, a numeric string, or a placeholder like '—' while
 * data is still loading — non-numeric targets are passed straight through, and
 * the tween kicks in automatically once a real number arrives (handy when the
 * stats API resolves after the element is already on screen).
 *
 * Respects prefers-reduced-motion (jumps straight to the final value).
 */
const easeOutCubic = (t) => 1 - (1 - t) ** 3;

const prefersReduced = () =>
  typeof window !== 'undefined'
  && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function useCountUp(target, { duration = 1300 } = {}) {
  const numeric = Number(target);
  const valid = Number.isFinite(numeric) && numeric > 0;

  const [display, setDisplay] = useState(valid ? 0 : target);
  const [inView, setInView] = useState(false);
  const doneRef = useRef(false);

  const setRef = useCallback((el) => {
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') { setInView(true); return; }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) { setInView(true); io.disconnect(); }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
  }, []);

  useEffect(() => {
    // Non-numeric (e.g. '—' placeholder): rendered straight through below; the
    // tween only runs once a real number arrives and the element is in view.
    if (!valid || !inView || doneRef.current) return undefined;

    doneRef.current = true;
    // Reduced motion → duration 0 makes the first frame land on the final value
    // (avoids a synchronous setState in the effect body).
    const dur = prefersReduced() ? 0 : duration;

    let raf = 0;
    const start = performance.now();
    const step = (now) => {
      const t = dur > 0 ? Math.min(1, (now - start) / dur) : 1;
      setDisplay(Math.round(numeric * easeOutCubic(t)));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [valid, inView, numeric, target, duration]);

  return [setRef, valid ? display : target];
}

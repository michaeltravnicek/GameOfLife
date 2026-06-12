import { useCallback, useEffect, useRef } from 'react';

/**
 * Lightweight scroll parallax. Returns a callback ref to attach to the element
 * you want to drift. On every scroll/resize (rAF-throttled, single passive
 * listener — same pattern as Nav.jsx) it computes the element's position in the
 * viewport and calls `apply(node, { offset, rect, vh })`.
 *
 * `offset` is 0 when the element is centered in the viewport and grows as it
 * moves away, scaled by `speed` — the default `apply` translates the element
 * vertically by `offset` for a classic background-lag effect.
 *
 * Pass `apply` to do something custom (e.g. fade hero content as it leaves).
 * Disabled automatically when the user prefers reduced motion, or via `disabled`
 * (so the same shared <Hero> can stay flat on the live homepage).
 */
const prefersReduced = () =>
  typeof window !== 'undefined'
  && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Never run scroll parallax on phones — the per-frame transform fights the URL-bar
// resize and reads as a jittery "jump" on scroll. Backgrounds stay flat on mobile.
const isMobileViewport = () =>
  typeof window !== 'undefined'
  && typeof window.matchMedia === 'function'
  && window.matchMedia('(max-width: 768px)').matches;

const defaultApply = (el, { offset }) => {
  el.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0)`;
};

export function useParallax({ speed = 0.15, apply = defaultApply, disabled = false } = {}) {
  const elRef = useRef(null);
  const rafRef = useRef(0);

  const setRef = useCallback((el) => { elRef.current = el; }, []);

  useEffect(() => {
    if (disabled || prefersReduced() || isMobileViewport()) return undefined;

    const tick = () => {
      rafRef.current = 0;
      const node = elRef.current;
      if (!node) return;
      const rect = node.getBoundingClientRect();
      const vh = window.innerHeight || 1;
      const center = rect.top + rect.height / 2;
      const offset = (vh / 2 - center) * speed;
      apply(node, { offset, rect, vh });
    };

    const onScroll = () => {
      if (rafRef.current) return;
      rafRef.current = requestAnimationFrame(tick);
    };

    tick();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [speed, apply, disabled]);

  return setRef;
}

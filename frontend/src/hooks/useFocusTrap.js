import { useEffect } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * While `active`, keep keyboard focus inside `ref`'s element: focus moves in on
 * activation, Tab and Shift+Tab cycle within it, and focus returns to where it
 * was afterwards. A dialog the keyboard can tab out of leaves the user on the
 * page underneath with no way back.
 */
export function useFocusTrap(ref, active) {
  useEffect(() => {
    const el = ref.current;
    if (!active || !el) return undefined;
    const previouslyFocused = document.activeElement;
    const focusables = () => Array.from(el.querySelectorAll(FOCUSABLE));
    (focusables()[0] || el).focus();

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
    el.addEventListener('keydown', onKey);
    return () => {
      el.removeEventListener('keydown', onKey);
      previouslyFocused?.focus?.();
    };
  }, [ref, active]);
}

import { useCallback, useEffect, useRef } from 'react';

/**
 * Shrink an element's text until it fits within `maxLines`, then leave it alone.
 *
 * Attach the returned ref to the text element. On mount, whenever `text`
 * changes, and whenever the element's box gets wider or narrower, the font size
 * is stepped down from whatever the stylesheet asked for until the rendered
 * height is within `maxLines` — or until `minFontSize`, which it never goes
 * below (better a clipped-looking third line than 9px of unreadable display
 * type). Text that already fits is never touched, so short names keep the full
 * CSS size.
 *
 * Why measure instead of picking a size from `name.length`, which is the trick
 * used for the event-detail place field: character count does not predict
 * wrapping. "Silent Disco, Brno 22.12.2025" and "Naked Ice Skating, Brno 10.12"
 * are both 29 characters, and on the homepage card the first fits at 28.5px
 * while the second needs 22.5px — it is the word lengths that decide where the
 * lines break, not the total.
 *
 * Writes straight to `style.fontSize` rather than through state: this runs
 * inside a layout read/write loop, and a re-render per step would be both
 * slower and pointless — nothing else on the page depends on the value.
 */
export function useFitText(text, { maxLines = 2, minFontSize = 14, extraHeight = 0 } = {}) {
  const ref = useRef(null);

  const fit = useCallback(() => {
    const el = ref.current;
    if (!el) return;

    // Start from the stylesheet's size, not last run's result, or repeated fits
    // would ratchet the text ever smaller.
    el.style.fontSize = '';
    const cs = getComputedStyle(el);
    const max = parseFloat(cs.fontSize);
    if (!max) return;
    const ratio = (parseFloat(cs.lineHeight) || max) / max;
    // `extraHeight` is whatever the box adds on top of the lines themselves —
    // a flex gap between stacked children, say — which no amount of shrinking
    // removes and which would otherwise be mistaken for an extra line.
    // +0.5 absorbs sub-pixel rounding in the measured height.
    const limit = (fs) => fs * ratio * maxLines + extraHeight + 0.5;

    if (el.getBoundingClientRect().height <= limit(max)) return;

    // Binary search the largest half-pixel size that fits. "Fits" is monotonic
    // in font size — if a size fits, every smaller one does — so this is safe
    // and costs ~6 measurements instead of the ~36 a linear walk would.
    let lo = minFontSize;
    let hi = max;
    while (hi - lo > 0.5) {
      const mid = Math.round(((lo + hi) / 2) * 2) / 2;
      el.style.fontSize = `${mid}px`;
      if (el.getBoundingClientRect().height <= limit(mid)) lo = mid;
      else hi = mid;
    }
    el.style.fontSize = `${lo}px`;
  }, [maxLines, minFontSize, extraHeight]);

  useEffect(() => {
    fit();

    // Re-fit on width changes only. Observing the parent's height would loop:
    // changing the font size changes the parent's height, which would fire the
    // observer, which would fit again.
    // Guarded because the fit above is the part that matters: where there is no
    // ResizeObserver (jsdom under test, an old browser) the text should still
    // be sized correctly for the width it rendered at, not take the card down
    // with a ReferenceError.
    let ro = null;
    if (typeof ResizeObserver !== 'undefined') {
      let lastWidth = 0;
      ro = new ResizeObserver((entries) => {
        const width = entries[0].contentRect.width;
        if (Math.abs(width - lastWidth) < 1) return;
        lastWidth = width;
        fit();
      });
      const box = ref.current?.parentElement;
      if (box) ro.observe(box);
    }

    // A late-arriving webfont changes the metrics after the first measurement.
    let cancelled = false;
    document.fonts?.ready.then(() => { if (!cancelled) fit(); }).catch(() => {});

    return () => {
      cancelled = true;
      ro?.disconnect();
    };
  }, [fit, text]);

  return ref;
}

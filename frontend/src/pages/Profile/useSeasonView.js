import { useMemo } from 'react';
import { seasonStats } from './seasonStats';

/**
 * Derive the per-season view model shared by the two profile-style pages
 * (ProfilePage and the anonymous PlayerPage): the stats object plus the sorted
 * upcoming/past event lists and the category breakdown.
 *
 * Runs unconditionally and tolerates a null `seasonData` (returns null `st` +
 * empty lists), so callers can keep it above their early returns and the hook
 * count stays stable across renders.
 */
export function useSeasonView(seasonData, today) {
  const st = useMemo(
    () => (seasonData ? seasonStats(seasonData, today) : null),
    [seasonData, today],
  );
  const upcoming = useMemo(
    () => (st ? st.future.slice().sort((a, b) => new Date(a.date) - new Date(b.date)) : []),
    [st],
  );
  const past = useMemo(
    () => (st ? st.past.slice().sort((a, b) => new Date(b.date) - new Date(a.date)) : []),
    [st],
  );
  const cats = useMemo(() => {
    if (!st) return { sorted: [], max: 1 };
    const buckets = {};
    st.evs.forEach((e) => {
      // Only real categories — uncategorized events don't form a fake bucket,
      // and the whole section hides when nothing remains.
      const cat = e.category?.name;
      if (!cat) return;
      if (!buckets[cat]) buckets[cat] = { n: 0, p: 0 };
      buckets[cat].n += 1;
      buckets[cat].p += e.pts || 0;
    });
    const sorted = Object.entries(buckets).sort((a, b) => b[1].p - a[1].p);
    const max = Math.max(...sorted.map(([, b]) => b.p), 1);
    return { sorted, max };
  }, [st]);

  return { st, upcoming, past, cats };
}

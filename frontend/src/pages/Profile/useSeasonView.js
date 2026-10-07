import { useMemo, useState } from 'react';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import { seasonStats } from './seasonStats';

export const TODAY = new Date();

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

/**
 * Season picking for a profile-style page. `payload` is the profile or player
 * response; `detail` names the lazily fetched per-season breakdown
 * (`{ key(seasonId), fetch(seasonId), enabled }`); `synthesize(payload)` builds
 * the summary shown when the payload has no seasons at all.
 *
 * The selected season is the explicit pick, else the newest one — derived, not
 * set in an effect, so it is right on the render the payload arrives. The
 * summary stands in for the detail until it loads, so the poster renders at once.
 */
export function useProfileSeason(payload, detail, synthesize) {
  const [pickedSeason, setPickedSeason] = useState(null);
  const seasonKey = pickedSeason ?? payload?.seasons?.[0]?.id ?? null;

  const { data: seasonDetail } = useCachedQuery(
    detail.key(seasonKey),
    () => detail.fetch(seasonKey),
    { enabled: detail.enabled && seasonKey != null, ttl: CACHE_TTL.PROFILE },
  );

  const summary = useMemo(() => {
    if (!payload) return null;
    const seasons = payload.seasons || [];
    if (seasons.length) return seasons.find((s) => s.id === seasonKey) || seasons[0];
    return synthesize(payload);
  }, [payload, seasonKey, synthesize]);
  const seasonData = (seasonDetail && seasonDetail.id === seasonKey) ? seasonDetail : summary;

  const seasonTabs = payload?.seasons?.map((s) => ({ key: s.id, label: s.label })) || [];
  return { seasonKey, setPickedSeason, seasonTabs, ...useSeasonView(seasonData, TODAY) };
}

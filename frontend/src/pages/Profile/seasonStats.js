// Shared per-season stats derivation for the profile-style pages
// (ProfilePage and the anonymous PlayerPage).
export function seasonStats(season, today) {
  // `season` may be a lightweight summary (no events, just season_pts) or the
  // full detail (with events). When events are present we derive everything from
  // them; otherwise we fall back to the summary's season_pts so the poster shows
  // the right total while the event list lazy-loads.
  const evs = [...(season.events || [])].sort((a, b) => new Date(a.date) - new Date(b.date));
  const past = evs.filter((e) => new Date(e.date) < today);
  const future = evs.filter((e) => new Date(e.date) >= today);
  // `|| 0` on every point value: under the owner's hide_pts flag the API sends
  // events with no `pts` at all, and a bare `a + undefined` would turn every
  // total on the page into NaN.
  const totalPts = evs.length ? evs.reduce((a, e) => a + (e.pts || 0), 0) : (season.season_pts || 0);
  const pastPts = past.reduce((a, e) => a + (e.pts || 0), 0);
  const futurePts = future.reduce((a, e) => a + (e.pts || 0), 0);
  const cities = [...new Set(evs.map((e) => e.place))];
  const rank = season.rank || (totalPts > 0 ? '—' : null);
  return { evs, past, future, totalPts, pastPts, futurePts, cities, start: new Date(season.start), end: new Date(season.end), label: season.label, rank };
}

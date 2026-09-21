import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchLeaderboard, fetchSeasons } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import PillTabs from '../../components/PillTabs/PillTabs';
import SearchInput from '../../components/SearchInput/SearchInput';
import Avatar from '../../components/Avatar/Avatar';
import PageHero from '../../components/PageHero/PageHero';
import PageStage from '../../components/PageStage/PageStage';
import PageState from '../../components/PageState/PageState';
import LoadMore from '../../components/LoadMore/LoadMore';
import Button from '../../components/Button/Button';
import PlayerRow, { playerLink } from '../../components/PlayerRow/PlayerRow';
import './LeaderboardPage.css';

const TROPHIES = ['🏆', '🥈', '🥉'];
// Rows shown under the podium before "Načíst další" (same pattern as events).
const REST_PAGE_SIZE = 50;

export default function LeaderboardPage() {
  // `seasonId` is what we send the API: 'active' (default), 'all', or a season id.
  const [seasonId, setSeasonId] = useState('active');
  const [query, setQuery] = useState('');
  // Visible-row cap per season tab (keyed so switching tabs starts fresh
  // without an effect-driven reset).
  const [restCounts, setRestCounts] = useState({});
  const restVisible = restCounts[seasonId] ?? REST_PAGE_SIZE;

  const { data: seasonsData } = useCachedQuery('seasons', fetchSeasons, { ttl: CACHE_TTL.LEADERBOARD });
  // Memoised, not `?? []`: a fresh [] each render gives every dependent
  // useMemo a new identity, so they all recompute on every render.
  const seasons = useMemo(() => seasonsData?.seasons || [], [seasonsData]);

  // Tabs: All-time + one per season. The active season's id-tab is highlighted
  // while the API param is still the resolver token 'active'.
  const activeSeason = useMemo(() => seasons.find((s) => s.is_active), [seasons]);
  const tabs = useMemo(
    () => [{ key: 'all', label: 'Celkem' }, ...seasons.map((s) => ({ key: String(s.id), label: s.name }))],
    [seasons],
  );
  const activeTab = seasonId === 'active'
    ? (activeSeason ? String(activeSeason.id) : 'all')
    : seasonId;

  const { data, loading: queryLoading, error, refetch } = useCachedQuery(
    `leaderboard:${seasonId}`,
    () => fetchLeaderboard(seasonId),
    { ttl: CACHE_TTL.LEADERBOARD },
  );
  const entries = useMemo(() => data?.entries || [], [data]);
  const loading = queryLoading && entries.length === 0;
  // A failed load must not read as "nobody on the leaderboard".
  const failed = !loading && !!error && entries.length === 0;

  const q = query.trim().toLowerCase();
  const top3 = entries.slice(0, 3);
  const rest = entries.slice(3);
  // podium display order: 2nd (left), 1st (center), 3rd (right)
  const podiumOrder = [1, 0, 2];

  // Derive `rest` inside the memo from `entries` (a stable cache reference).
  // The outer `rest` above is a fresh array every render, so depending on it
  // made this memo recompute every render and re-filter even while typing.
  // Search looks through EVERY player (cap ignored); otherwise the list is
  // capped and grown by the "Načíst další" button below.
  const { visibleRest, remaining } = useMemo(() => {
    const r = entries.slice(3);
    if (q) return { visibleRest: r.filter((p) => p.name.toLowerCase().includes(q)), remaining: 0 };
    return { visibleRest: r.slice(0, restVisible), remaining: Math.max(r.length - restVisible, 0) };
  }, [entries, q, restVisible]);

  return (
    <div className="leaderboard-page has-stage">
      <PageStage image="gal1" position="center 15%" tint="alive" grain="blue" />

      <PageHero
        eyebrow={`Ranking · ${data?.season?.name || 'Celkem'}`}
        title="Leaderboard"
      />

      <section className="controls">
        <PillTabs
          tabs={tabs}
          active={activeTab}
          onChange={setSeasonId}
        />
        <SearchInput
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Vyhledat hráče…"
          variant="frost"
          className="lb-search"
        />
        <Button as="link" to="/o-bodech" variant="pill" className="lb-help-link">
          <span className="lb-help-q" aria-hidden="true">?</span>
          Co jsou body?
        </Button>
      </section>

      <main className="lb-main">
        {loading && <PageState kind="loading" text="Načítám žebříček…" />}

        {failed && (
          <PageState kind="error" text="Žebříček se nepodařilo načíst. Zkontroluj připojení a zkus to znovu." onRetry={refetch} busy={queryLoading} />
        )}

        {!loading && !failed && entries.length === 0 && (
          <PageState kind="empty" text="Žádní hráči na žebříčku." />
        )}

        {!loading && top3.length > 0 && (
          <div className="stage-wrap">
            <div className="podium">
              {podiumOrder.map((idx) => {
                const p = top3[idx];
                if (!p) return null;
                const cls = idx === 0 ? 'p1' : idx === 1 ? 'p2' : 'p3';
                const dim = q && !p.name.toLowerCase().includes(q);
                return (
                  <Link
                    key={p.id}
                    to={playerLink(p)}
                    className={`pod ${cls} clickable${dim ? ' dim' : ''}`}
                  >
                    <div className="trophy">{TROPHIES[idx]}</div>
                    {/* The podium is the top three, so it always gets the photo
                        (initials when there isn't one) — see PlayerRow for the
                        same cut applied to the list below. */}
                    <Avatar name={p.name} photo={p.photo} size={idx === 0 ? 'xl' : 'lg'} rank={idx === 0 ? 'gold' : idx === 1 ? 'silver' : 'bronze'} className="ava" />
                    <div className="nm">{p.name}</div>
                    <div className="pts">{p.total_points}<span className="pts-u">pts</span></div>
                    <div className="base"><span className="rk">{idx + 1}</span></div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {!loading && rest.length > 0 && (
          <>
            <div className="gol-flank list-label">Další hráči</div>
            <div className="gol-card gol-card--flush list">
              <div className="list-inner">
                {visibleRest.length === 0 && q ? (
                  <PageState kind="empty" compact text="Nikdo nenalezen." />
                ) : (
                  visibleRest.map((p) => (
                    <PlayerRow key={p.id} player={p} />
                  ))
                )}
              </div>
            </div>
            {remaining > 0 && (
              <LoadMore
                remaining={remaining}
                onClick={() => setRestCounts((c) => ({ ...c, [seasonId]: restVisible + REST_PAGE_SIZE }))}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

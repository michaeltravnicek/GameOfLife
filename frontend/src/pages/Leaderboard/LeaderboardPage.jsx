import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchLeaderboard, fetchSeasons } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import PillTabs from '../../components/PillTabs/PillTabs';
import SearchInput from '../../components/SearchInput/SearchInput';
import Avatar from '../../components/Avatar/Avatar';
import PageHero from '../../components/PageHero/PageHero';
import PlayerRow, { playerLink } from '../../components/PlayerRow/PlayerRow';
import './LeaderboardPage.css';

const TROPHIES = ['🏆', '🥈', '🥉'];

export default function LeaderboardPage() {
  // `seasonId` is what we send the API: 'active' (default), 'all', or a season id.
  const [seasonId, setSeasonId] = useState('active');
  const [query, setQuery] = useState('');

  const { data: seasonsData } = useCachedQuery('seasons', fetchSeasons, { ttl: CACHE_TTL.LEADERBOARD });
  const seasons = seasonsData?.seasons || [];

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

  const { data, loading: queryLoading } = useCachedQuery(
    `leaderboard:${seasonId}`,
    () => fetchLeaderboard(seasonId),
    { ttl: CACHE_TTL.LEADERBOARD },
  );
  const entries = data?.entries || [];
  const loading = queryLoading && entries.length === 0;

  const q = query.trim().toLowerCase();
  const top3 = entries.slice(0, 3);
  const rest = entries.slice(3);
  // podium display order: 2nd (left), 1st (center), 3rd (right)
  const podiumOrder = [1, 0, 2];

  // Derive `rest` inside the memo from `entries` (a stable cache reference).
  // The outer `rest` above is a fresh array every render, so depending on it
  // made this memo recompute every render and re-filter even while typing.
  const visibleRest = useMemo(() => {
    const r = entries.slice(3);
    return q ? r.filter((p) => p.name.toLowerCase().includes(q)) : r;
  }, [entries, q]);

  return (
    <div className="leaderboard-page">
      <div className="stage" />
      <div className="grain" />

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
          className="lb-search"
        />
        <Link to="/o-bodech" className="lb-help-link">Co jsou body?</Link>
      </section>

      <main className="lb-main">
        {loading && <div className="empty">Načítám…</div>}

        {!loading && entries.length === 0 && (
          <div className="empty">Žádní hráči na žebříčku.</div>
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
            <div className="list-label">Další hráči</div>
            <div className="list">
              <div className="list-inner">
                {visibleRest.length === 0 && q ? (
                  <div className="empty">Nikdo nenalezen.</div>
                ) : (
                  visibleRest.map((p) => (
                    <PlayerRow key={p.id} player={p} />
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

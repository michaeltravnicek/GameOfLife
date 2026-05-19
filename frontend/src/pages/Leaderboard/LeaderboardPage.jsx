import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchLeaderboard } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import TabBar from '../../components/TabBar/TabBar';
import SearchInput from '../../components/SearchInput/SearchInput';
import Avatar from '../../components/Avatar/Avatar';
import './LeaderboardPage.css';

const TROPHIES = ['🏆', '🥈', '🥉'];

const LB_TABS = [
  { key: 'total', label: 'Celkem' },
  { key: 'month', label: 'Tento rok' },
];

export default function LeaderboardPage() {
  const [tab, setTab] = useState('total');
  const [query, setQuery] = useState('');

  // Cached per period — server itself caches for 5 min, so we mirror that.
  const period = tab === 'month' ? 'month' : 'total';
  const { data, loading: queryLoading } = useCachedQuery(
    `leaderboard:${period}`,
    () => fetchLeaderboard(period),
    { ttl: 5 * 60 * 1000 },
  );
  const entries = data?.entries || [];
  const loading = queryLoading && entries.length === 0;

  const q = query.trim().toLowerCase();
  const top3 = entries.slice(0, 3);
  const rest = entries.slice(3);
  // podium display order: 2nd (left), 1st (center), 3rd (right)
  const podiumOrder = [1, 0, 2];

  const visibleRest = useMemo(
    () => (q ? rest.filter((p) => p.name.toLowerCase().includes(q)) : rest),
    [rest, q],
  );

  return (
    <div className="leaderboard-page">
      <div className="stage" />
      <div className="grain" />

      <header className="hero">
        <div className="eyebrow">Ranking · Sezóna 2025/26</div>
        <h1>Leaderboard</h1>
        <div className="divider" />
      </header>

      <section className="controls">
        <TabBar
          tabs={LB_TABS}
          active={tab}
          onChange={setTab}
        />
        <SearchInput
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Vyhledat hráče…"
          className="lb-search"
        />
        <Link to="/o-bodech" className="lb-help-link">Co jsou to body?</Link>
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
                const profileLink = p.profile_username ? `/profil/${p.profile_username}` : null;
                return profileLink ? (
                  <Link
                    key={p.id}
                    to={profileLink}
                    className={`pod ${cls} clickable`}
                    style={dim ? { opacity: 0.22 } : undefined}
                  >
                    <div className="trophy">{TROPHIES[idx]}</div>
                    <Avatar name={p.name} size={idx === 0 ? 'xl' : 'lg'} rank={idx === 0 ? 'gold' : idx === 1 ? 'silver' : 'bronze'} className="ava" />
                    <div className="nm">{p.name}</div>
                    <div className="pts">{p.total_points}<span className="pts-u">pts</span></div>
                    <div className="base"><span className="rk">{idx + 1}</span></div>
                  </Link>
                ) : (
                  <div
                    key={p.id}
                    className={`pod ${cls}`}
                    style={dim ? { opacity: 0.22 } : undefined}
                  >
                    <div className="trophy">{TROPHIES[idx]}</div>
                    <Avatar name={p.name} size={idx === 0 ? 'xl' : 'lg'} rank={idx === 0 ? 'gold' : idx === 1 ? 'silver' : 'bronze'} className="ava" />
                    <div className="nm">{p.name}</div>
                    <div className="pts">{p.total_points}<span className="pts-u">pts</span></div>
                    <div className="base"><span className="rk">{idx + 1}</span></div>
                  </div>
                );
              })}
            </div>
            <div className="stage-floor" />
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
                  visibleRest.map((p) => {
                    const profileLink = p.profile_username ? `/profil/${p.profile_username}` : null;
                    return profileLink ? (
                      <Link
                        key={p.id}
                        to={profileLink}
                        className="row clickable"
                      >
                        <div className="rk">{p.rank}.</div>
                        <div className="nm">
                          <Avatar name={p.name} size="sm" />
                          <span className="txt">{p.name}</span>
                        </div>
                        <div className="pt">{p.total_points}<span className="u">pts</span></div>
                      </Link>
                    ) : (
                      <div key={p.id} className="row">
                        <div className="rk">{p.rank}.</div>
                        <div className="nm">
                          <Avatar name={p.name} size="sm" />
                          <span className="txt">{p.name}</span>
                        </div>
                        <div className="pt">{p.total_points}<span className="u">pts</span></div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchLeaderboard } from '../../services/api';
import './LeaderboardPage.css';

const TROPHIES = ['🏆', '🥈', '🥉'];
const initials = (n) =>
  (n || '').split(' ').map((w) => w[0]).filter(Boolean).join('').slice(0, 2).toUpperCase();

export default function LeaderboardPage() {
  const [tab, setTab] = useState('total');
  const [query, setQuery] = useState('');
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchLeaderboard(tab === 'month' ? 'month' : 'total')
      .then((d) => setEntries(d.entries || []))
      .finally(() => setLoading(false));
  }, [tab]);

  const q = query.trim().toLowerCase();
  const top3 = entries.slice(0, 3);
  const rest = entries.slice(3);
  const podiumOrder = [1, 0, 2];

  const visibleRest = useMemo(
    () => rest.filter((p) => !q || p.name.toLowerCase().includes(q)),
    [rest, q],
  );

  return (
    <div className="leaderboard-page">
      <div className="stage" />
      <div className="grain" />

      <header className="hero">
        <div className="eyebrow">Ranking · Sezóna 2025/26</div>
        <h1>Leaderboard</h1>
        <p className="tagline">Kdo hraje nejtvrději. Body za účast a odvahu jít mimo komfortní zónu.</p>
        <div className="divider" />
      </header>

      <section className="controls">
        <div className="tabs">
          <button className={`tab${tab === 'total' ? ' on' : ''}`} onClick={() => setTab('total')}>Celkem</button>
          <button className={`tab${tab === 'month' ? ' on' : ''}`} onClick={() => setTab('month')}>Tento rok</button>
        </div>
        <div className="search">
          <input
            type="text"
            placeholder="Vyhledat hráče…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoComplete="off"
          />
        </div>
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
              {podiumOrder.map((i) => {
                const p = top3[i];
                if (!p) return null;
                const cls = i === 0 ? 'p1' : i === 1 ? 'p2' : 'p3';
                const dim = q && !p.name.toLowerCase().includes(q);
                const link = p.profile_username ? `/profil/${p.profile_username}` : null;
                const Wrap = link ? Link : 'div';
                return (
                  <Wrap
                    key={p.id}
                    to={link || undefined}
                    className={`pod ${cls}`}
                    style={{
                      ...(dim ? { opacity: 0.22 } : {}),
                      ...(link ? { textDecoration: 'none', color: 'inherit' } : {}),
                    }}
                  >
                    <div className="trophy">{TROPHIES[i]}</div>
                    <div className="ava">{initials(p.name)}</div>
                    <div className="nm">{p.name}</div>
                    <div className="pts">{p.total_points}<span className="pts-u">pts</span></div>
                    <div className="base"><span className="rk">{i + 1}</span></div>
                  </Wrap>
                );
              })}
            </div>
            <div className="stage-floor" />
          </div>
        )}

        {rest.length > 0 && (
          <>
            <div className="list-label">Další hráči</div>
            <div className="list">
              <div className="list-inner">
                {visibleRest.length === 0 && q ? (
                  <div className="empty">Nikdo nenalezen.</div>
                ) : (
                  rest.map((p) => {
                    const hidden = q && !p.name.toLowerCase().includes(q);
                    if (hidden) return null;
                    const link = p.profile_username ? `/profil/${p.profile_username}` : null;
                    const Wrap = link ? Link : 'div';
                    return (
                      <Wrap
                        key={p.id}
                        to={link || undefined}
                        className="row"
                        style={link ? { textDecoration: 'none', color: 'inherit' } : undefined}
                      >
                        <div className="rk">{p.rank}.</div>
                        <div className="nm">
                          <div className="av">{initials(p.name)}</div>
                          <span className="txt">{p.name}</span>
                        </div>
                        <div className="pt">{p.total_points}<span className="u">pts</span></div>
                      </Wrap>
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

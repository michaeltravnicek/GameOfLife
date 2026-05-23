import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PillTabs from '../../components/PillTabs/PillTabs';
import PointsChart from './PointsChart';
import './ProfilePage.css';

const TODAY = new Date('2026-04-29');
const MONTHS_SHORT = ['LED', 'ÚNO', 'BŘE', 'DUB', 'KVĚ', 'ČER', 'ČVC', 'SRP', 'ZÁŘ', 'ŘÍJ', 'LIS', 'PRO'];

const SEASONS = {
  '25/26': {
    label: '25/26', start: '2025-04-01', end: '2026-03-31',
    pos: { n: '#01', sub: <><strong>Lídr</strong> · 240 pts náskok</> },
    events: [
      { cat: 'Karaoke', nm: 'Karaoke TOUR 2025', city: 'Ostrava', loc: 'Stodolní', date: '2025-11-20', pts: 70 },
      { cat: 'Akce', nm: 'Deskovky Night', city: 'Plzeň', loc: 'Centrum', date: '2025-11-05', pts: 30 },
      { cat: 'Akce', nm: 'Kokosy na sněhu', city: 'Beskydy', loc: 'Pustevny', date: '2025-12-15', pts: 100 },
      { cat: 'Běh', nm: 'Christmas Run', city: 'Brno', loc: 'Náměstí Svobody', date: '2025-12-22', pts: 80 },
      { cat: 'Bruslení', nm: 'Naked Ice Skating', city: 'Praha', loc: 'Štvanice', date: '2026-01-18', pts: 100 },
      { cat: 'Tanec', nm: 'GoL Dance Class', city: 'Praha', loc: 'Karlín', date: '2026-05-18', pts: 50 },
      { cat: 'Běh', nm: 'C50', city: 'Brno', loc: 'Bystrc', date: '2026-06-02', pts: 120 },
    ],
  },
  '24/25': {
    label: '24/25', start: '2024-04-01', end: '2025-03-31',
    pos: { n: '#03', sub: <><strong>3. místo</strong> · solidní sezóna</> },
    events: [
      { cat: 'Tanec', nm: 'Dance Class Jaro', city: 'Praha', loc: 'Karlín', date: '2024-05-15', pts: 50 },
      { cat: 'Běh', nm: 'C50 2024', city: 'Brno', loc: 'Bystrc', date: '2024-06-08', pts: 120 },
      { cat: 'Běh', nm: 'Naked Mile', city: 'Olomouc', loc: 'Smetanovy sady', date: '2024-07-04', pts: 80 },
      { cat: 'Akce', nm: 'Letní festival', city: 'Český Krumlov', loc: 'Náměstí', date: '2024-08-20', pts: 90 },
      { cat: 'Karaoke', nm: 'Karaoke Open Mic', city: 'Brno', loc: 'Stará Pekárna', date: '2024-09-12', pts: 50 },
      { cat: 'Bruslení', nm: 'Ice Run', city: 'Liberec', loc: 'Tipsport Arena', date: '2025-02-08', pts: 80 },
      { cat: 'Běh', nm: 'Vinohradský běh', city: 'Praha', loc: 'Vinohrady', date: '2025-03-15', pts: 70 },
    ],
  },
  '23/24': {
    label: '23/24', start: '2023-04-01', end: '2024-03-31',
    pos: { n: '#28', sub: <><strong>Nováček</strong> · jen pár akcí</> },
    events: [
      { cat: 'Akce', nm: 'Welcome to Game of Life', city: 'Brno', loc: 'Centrum', date: '2024-02-20', pts: 30 },
      { cat: 'Běh', nm: 'První míle', city: 'Brno', loc: 'Mendelovo nám.', date: '2024-03-10', pts: 25 },
    ],
  },
};

const HIGHLIGHTS = [
  { body: <><strong>Vyhrál Naked Ice Skating</strong> na Štvanici — nejnižší teplota, nejvyšší ego.</>, tag: '01 / 2026 · +100 pts' },
  { body: <><strong>Doběhl Christmas Run</strong> bez zastávky, i když venku bylo −7 °C.</>, tag: '12 / 2025 · +80 pts' },
  { body: <><strong>Vystoupil na karaoke túře</strong> ve třech městech za jeden víkend.</>, tag: '11 / 2025 · +70 pts' },
  { body: <><strong>Drží 1. místo</strong> na leaderboardu už šestý měsíc v řadě.</>, tag: 'Sezóna 25/26' },
];

const ALL_TOTAL = Object.values(SEASONS).reduce((a, s) => a + s.events.reduce((b, e) => b + e.pts, 0), 0);

function seasonStats(key) {
  const s = SEASONS[key];
  const evs = [...s.events].sort((a, b) => new Date(a.date) - new Date(b.date));
  const past = evs.filter((e) => new Date(e.date) < TODAY);
  const future = evs.filter((e) => new Date(e.date) >= TODAY);
  const totalPts = evs.reduce((a, e) => a + e.pts, 0);
  const pastPts = past.reduce((a, e) => a + e.pts, 0);
  const futurePts = future.reduce((a, e) => a + e.pts, 0);
  const cities = [...new Set(evs.map((e) => e.city))];
  return { evs, past, future, totalPts, pastPts, futurePts, cities, start: new Date(s.start), end: new Date(s.end), label: s.label, pos: s.pos };
}

function EventRow({ e, rank, kind }) {
  const d = new Date(e.date);
  return (
    <div className={`row ${kind}`}>
      <span className="rk">{String(rank).padStart(2, '0')}</span>
      <span className="cat">{e.cat}</span>
      <div className="info"><div className="nm">{e.nm}</div><div className="loc">{e.city}, {e.loc}</div></div>
      <div className="dt">{d.getDate()}. {MONTHS_SHORT[d.getMonth()]} {String(d.getFullYear()).slice(2)}</div>
      <div className="pt">+{e.pts}<span className="u">pts</span></div>
    </div>
  );
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const [seasonKey, setSeasonKey] = useState('25/26');
  const [view, setView] = useState('about');

  const st = useMemo(() => seasonStats(seasonKey), [seasonKey]);

  const upcoming = useMemo(() => st.future.slice().sort((a, b) => new Date(a.date) - new Date(b.date)), [st]);
  const past = useMemo(() => st.past.slice().sort((a, b) => new Date(b.date) - new Date(a.date)), [st]);

  const cats = useMemo(() => {
    const buckets = {};
    st.evs.forEach((e) => { if (!buckets[e.cat]) buckets[e.cat] = { n: 0, p: 0 }; buckets[e.cat].n += 1; buckets[e.cat].p += e.pts; });
    const sorted = Object.entries(buckets).sort((a, b) => b[1].p - a[1].p);
    const max = Math.max(...sorted.map(([, b]) => b.p), 1);
    return { sorted, max };
  }, [st]);

  const best = useMemo(() => st.evs.slice().sort((a, b) => b.pts - a.pts)[0], [st]);
  const avg = st.evs.length ? Math.round(st.totalPts / st.evs.length) : 0;
  const seasonLabel = `Sezóna 20${st.label.replace('/', '/20')}`;

  const handleShare = () => {
    const url = window.location.href;
    if (navigator.share) navigator.share({ title: 'Lukáš Müller — Game of Life', url }).catch(() => {});
    else navigator.clipboard?.writeText(url);
  };

  const seasonTabs = Object.keys(SEASONS).map((k) => ({ key: k, label: k }));
  const viewTabs = [
    { key: 'about', label: 'O mně' },
    { key: 'events', label: 'Akce', badge: st.evs.length },
    { key: 'points', label: 'Body', badge: st.totalPts },
  ];

  return (
    <div className="profile-page">
      <section className="poster">
        <div className="poster-img" />
        <div className="poster-grain" />
        <div className="poster-vignette" />

        <div className="poster-top">
          <div className="badges">
            <span className="ev-pill live">★ {st.pos.n} Leaderboard</span>
            <span className="ev-pill">{seasonLabel}</span>
          </div>
          <div className="poster-avatar">LM</div>
          <h1 className="poster-name">Lukáš Müller</h1>
          <div className="poster-handle">@lukasmuller · hraje od 02 / 2024</div>
        </div>

        <div className="credits">
          <span className="credits-rule" />
          <div className="credit">
            <div className="credit-label">— Body —</div>
            <div className="credit-value">{st.totalPts}</div>
            <div className="credit-sub"><strong>{st.cities.length} měst</strong> · {st.future.length ? 'aktivní sezóna' : 'sezóna ukončena'}</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Akcí —</div>
            <div className="credit-value">{st.evs.length}</div>
            <div className="credit-sub"><strong>{st.past.length} absolv.</strong> · {st.future.length} nadch.</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Pozice —</div>
            <div className="credit-value">{st.pos.n}</div>
            <div className="credit-sub">{st.pos.sub}</div>
          </div>
        </div>
      </section>

      <div className="action-bar">
        <div className="action-inner">
          <PillTabs tabs={seasonTabs} active={seasonKey} onChange={setSeasonKey} />
          <PillTabs tabs={viewTabs} active={view} onChange={setView} />
        </div>
      </div>

      <div className="body-wrap">
        <main className="profile-main">
          <section className="profile-view" key={view}>
            {view === 'about' && (
              <>
                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 01 · O mně —</span><span className="meta">profil &amp; minulost</span></div>
                  <h2 className="sec-heading">Hraj naplno, <span className="pink">nebo vůbec.</span></h2>
                  <p className="about-quote">Karaoke v sobotu, deskovky ve středu, nahá míle kdykoliv. Každá akce je výmluva potkat lidi, co mají života plné zuby — a chtějí ho prožít naplno.</p>
                  <div className="about-meta">
                    <span>Brno · CZ</span><span className="dot" />
                    <span>Běh · Tanec · Karaoke</span><span className="dot" />
                    <span>Připojil se 02 / 2024</span>
                  </div>

                  <div className="factgrid">
                    <div className="fact"><div className="l">Domácí město</div><div className="v">Brno</div><div className="s">Kde nejvíc běhá &amp; zpívá</div></div>
                    <div className="fact"><div className="l">Hraje od</div><div className="v">02 / 2024</div><div className="s">{Object.keys(SEASONS).length} sezóny v řadě</div></div>
                    <div className="fact"><div className="l">Celkem bodů</div><div className="v">{ALL_TOTAL}</div><div className="s">napříč všemi sezónami</div></div>
                  </div>

                  <div className="socials">
                    <div className="socials-label">— Najdeš ho na —</div>
                    <div className="socials-grid">
                      <a className="social" href="https://instagram.com/lukasmuller" target="_blank" rel="noopener noreferrer">
                        <span className="ico">IG</span>
                        <span className="lbl"><span className="p">Instagram</span><span className="h">@lukasmuller</span></span>
                        <span className="arr">↗</span>
                      </a>
                      <a className="social" href="https://strava.com/athletes/lukasmuller" target="_blank" rel="noopener noreferrer">
                        <span className="ico">ST</span>
                        <span className="lbl"><span className="p">Strava</span><span className="h">Lukáš M.</span></span>
                        <span className="arr">↗</span>
                      </a>
                      <a className="social" href="https://open.spotify.com/user/lukasmuller" target="_blank" rel="noopener noreferrer">
                        <span className="ico">SP</span>
                        <span className="lbl"><span className="p">Spotify</span><span className="h">karaoke playlist</span></span>
                        <span className="arr">↗</span>
                      </a>
                      <a className="social" href="mailto:lukas@lukasmuller.cz">
                        <span className="ico">@</span>
                        <span className="lbl"><span className="p">E-mail</span><span className="h">lukas@lukasmuller.cz</span></span>
                        <span className="arr">↗</span>
                      </a>
                    </div>
                  </div>
                </div>

                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 02 · Highlighty —</span><span className="meta">co se mu povedlo</span></div>
                  <h2 className="sec-heading">Trofeje &amp; momenty.</h2>
                  <ol className="highlights">
                    {HIGHLIGHTS.map((h, i) => (
                      <li key={i}>
                        <span className="h-body">{h.body}</span>
                        <span className="h-tag">{h.tag}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </>
            )}

            {view === 'events' && (
              <>
                {upcoming.length > 0 && (
                  <div className="section">
                    <div className="sec-rule" />
                    <div className="sec-eyebrow"><span>— 03 · Nadcházející —</span><span className="meta">+{st.futurePts} pts na cestě</span></div>
                    <h2 className="sec-heading">Co ho <span className="pink">čeká.</span></h2>
                    <div className="list"><div className="list-inner">
                      {upcoming.map((e, i) => <EventRow key={e.nm} e={e} rank={i + 1} kind="future" />)}
                    </div></div>
                  </div>
                )}

                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 04 · Absolvované —</span><span className="meta">+{st.pastPts} pts zatím</span></div>
                  <h2 className="sec-heading">Co má <span className="pink">za sebou.</span></h2>
                  <div className="list"><div className="list-inner">
                    {past.length
                      ? past.map((e, i) => <EventRow key={e.nm} e={e} rank={i + 1} kind="past" />)
                      : <div className="empty">Zatím žádné absolvované akce v této sezóně.</div>}
                  </div></div>
                </div>
              </>
            )}

            {view === 'points' && (
              <>
                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 05 · Body v čase —</span><span className="meta">křivka sezóny</span></div>
                  <h2 className="sec-heading">Křivka <span className="pink">sezóny.</span></h2>

                  <div className="chart-card">
                    <div className="chart-meta">
                      <div>
                        <div className="l">Celkem v sezóně</div>
                        <div className="total">{st.totalPts}<small>pts</small></div>
                      </div>
                      <div className="legend">
                        <span><i />Absolvováno</span>
                        <span><i className="dashed" />Nadcházející</span>
                        <span style={{ color: '#f5c842' }}><i style={{ background: '#f5c842' }} />Dnes</span>
                      </div>
                    </div>
                    <PointsChart stats={st} today={TODAY} />
                    <div className="mini-stats">
                      <div className="mini"><div className="l">Absolvováno</div><div className="v pink">{st.pastPts}</div><div className="s">bodů zatím</div></div>
                      <div className="mini"><div className="l">Nadcházející</div><div className="v">{st.futurePts}</div><div className="s">bodů na cestě</div></div>
                      <div className="mini"><div className="l">Nejlepší akce</div><div className="v yellow">{best ? `+${best.pts}` : '—'}</div><div className="s">{best ? best.nm : 'zatím nic'}</div></div>
                      <div className="mini"><div className="l">Průměr / akce</div><div className="v">{avg}</div><div className="s">bodů</div></div>
                    </div>
                  </div>
                </div>

                <div className="section">
                  <div className="sec-rule" />
                  <div className="sec-eyebrow"><span>— 06 · Kategorie —</span><span className="meta">{cats.sorted.length} kategorií</span></div>
                  <h2 className="sec-heading">V čem <span className="pink">jede.</span></h2>
                  <div className="cat-list">
                    {cats.sorted.length
                      ? cats.sorted.map(([cat, b]) => (
                        <div className="cat-row" key={cat}>
                          <span className="name">{cat}</span>
                          <span className="bar"><i style={{ width: `${Math.round((b.p / cats.max) * 100)}%` }} /></span>
                          <span className="meta">{b.n}× · <b>+{b.p}</b></span>
                        </div>
                      ))
                      : <div className="empty">Žádná data v této sezóně.</div>}
                  </div>
                </div>
              </>
            )}
          </section>
        </main>
      </div>

      <div className="back-strip">
        <div className="back-strip-inner">
          <Link className="back-link" to="/">← Zpět na hlavní stránku</Link>
          <div className="back-actions">
            <Link className="btn-cta" to="/upravit-profil">✎ Upravit profil</Link>
            <button type="button" className="btn-cta ghost" onClick={handleShare}>Sdílet profil</button>
            <button type="button" className="btn-cta ghost" onClick={() => navigate('/')}>Odhlásit se</button>
          </div>
        </div>
      </div>
    </div>
  );
}

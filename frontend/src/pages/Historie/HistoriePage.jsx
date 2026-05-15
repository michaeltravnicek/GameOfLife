import './HistoriePage.css';

const chapters = [
  {
    roman: 'I',
    year: '2021',
    yearWords: 'Two‑Thousand Twenty‑One',
    subtitle: 'Kde to všechno začalo',
    entries: [
      {
        season: 'Jaro',
        tag: 'Začátek',
        title: 'Zrození Game of Life',
        body: 'Vše začalo jednoduchou myšlenkou — přestat jen přemýšlet a začít skutečně žít. Parta přátel se sešla u prvního společného výletu a rozhodla, že z toho udělá zvyk. Pravidla byla jednoduchá: přijít, zažít, opakovat.',
        statLabel: 'Zakladatelů',
        statValue: '05',
        archive: '001',
      },
      {
        season: 'Léto',
        tag: 'První sezóna',
        title: 'Rosteme',
        body: 'Slovo se šíří. Po prvních akcích — výletech, sportovních výzvách a workshopech — se ke komunitě přidávají noví lidé. Formuje se první neoficiální leaderboard na papíře a rozjíždí se pravidelný rytmus akcí.',
        statLabel: 'Členů · Akcí',
        statValue: '20 · 08',
        archive: '002',
      },
      {
        season: 'Podzim',
        tag: 'Systém',
        title: 'První Leaderboard',
        body: 'Bodový systém dostává jasná pravidla. Každá akce má hodnotu, každý účastník sbírá body. Vzniká první digitální žebříček — a s ním i zdravé soutěžení, které komunitu stmeluje místo toho, aby ji rozdělilo.',
        statLabel: 'Vítěz sezóny',
        statValue: '№ 01',
        archive: '003',
      },
    ],
  },
  {
    roman: 'II',
    year: '2022',
    yearWords: 'Two‑Thousand Twenty‑Two',
    subtitle: 'Hra dostává tvar',
    entries: [
      {
        season: 'Jaro',
        tag: 'Komunita',
        title: '50 členů & Instagram',
        body: 'Game of Life překračuje hranici 50 aktivních členů a spouští Instagram. Pravidelné posty, fotky z akcí a zákulisí přitahují nové lidi. Akce se diverzifikují — tanec, lezení, jazykové výzvy, meditace.',
        statLabel: 'Členů · Kanál',
        statValue: '50 · @gameofyolo',
        archive: '004',
      },
      {
        season: 'Podzim',
        tag: 'Online',
        title: 'Spuštění gameofyolo.com',
        body: 'Komunita dostává svůj digitální domov. Web přináší přehled akcí, veřejný leaderboard a možnost přihlásit se na akce online. Správa komunity se profesionalizuje a databáze hráčů roste.',
        statLabel: 'Doména',
        statValue: 'gameofyolo.com',
        archive: '005',
      },
    ],
  },
  {
    roman: 'III',
    year: '2023',
    yearWords: 'Two‑Thousand Twenty‑Three',
    subtitle: 'Magická stovka',
    entries: [
      {
        season: 'Jaro',
        tag: 'Milestone',
        title: '100 aktivních hráčů',
        body: 'Magická stovka. Game of Life slaví s výjezdním víkendem pro celou komunitu — největší akcí v historii. Vzniká fotogalerie, kde si hráči sdílejí vlastní záběry z akcí a zachycují společné vzpomínky.',
        statLabel: 'Hráčů · Galerie',
        statValue: '100 · live',
        archive: '006',
      },
    ],
  },
  {
    roman: 'IV',
    year: '2024',
    yearWords: 'Two‑Thousand Twenty‑Four',
    subtitle: 'Zralá sezóna',
    entries: [
      {
        season: 'Celý rok',
        tag: 'Evoluce',
        title: 'Nová sezóna, nové funkce',
        body: 'Redesign webu, srdíčka na fotky, profily hráčů a propracovanější bodový systém. Komunita se stává zralejší — vědomě buduje kulturu vzájemné podpory a odvahy jít mimo komfortní zónu.',
        statLabel: 'Profily · Lajky · Žebříček',
        statValue: 'v 2.0',
        archive: '007',
      },
    ],
  },
  {
    roman: 'V',
    year: '2025',
    yearWords: 'Two‑Thousand Twenty‑Five',
    subtitle: 'Příběh se píše dál',
    closing: true,
    entries: [
      {
        season: 'Teď',
        tag: 'Přítomnost',
        title: 'Stále v pohybu',
        body: 'Game of Life pokračuje. Každý měsíc nové akce, každá sezóna nové výzvy. Příběh se píše dál — a ty jsi jeho součástí. Přidej se, sbírej body a dokaž, že život stojí za to žít naplno.',
        statLabel: 'Status',
        statValue: 'OPEN',
        archive: '008',
        live: true,
      },
    ],
  },
];

const yearIndex = chapters.map(c => c.year);

export default function HistoriePage() {
  return (
    <div className="hist-page">
      <div className="hist-stage" aria-hidden="true" />
      <div className="hist-grain" aria-hidden="true" />
      <div className="hist-vignette" aria-hidden="true" />

      <header className="hist-hero">
        <div className="hist-hero-meta">
          <span className="hist-hero-vol">Vol. 01</span>
          <span className="hist-hero-rule" />
          <span className="hist-hero-range">2021 — 2025</span>
        </div>

        <h1 className="hist-hero-title">
          <span className="hist-hero-line hist-hero-line-1">Histo</span>
          <span className="hist-hero-line hist-hero-line-2">rie<span className="hist-hero-mark">*</span></span>
        </h1>

        <p className="hist-hero-tagline">
          Od party přátel <em>ke komunitě stovek lidí</em> — kronika toho,
          jak vznikl a rostl Game&nbsp;of&nbsp;Life.
        </p>

        <aside className="hist-hero-toc" aria-label="Obsah">
          <span className="hist-toc-label">Obsah</span>
          <ol className="hist-toc-list">
            {chapters.map((c, i) => (
              <li key={c.year}>
                <a href={`#chapter-${c.year}`}>
                  <span className="hist-toc-roman">{c.roman}</span>
                  <span className="hist-toc-year">{c.year}</span>
                  <span className="hist-toc-sub">{c.subtitle}</span>
                </a>
              </li>
            ))}
          </ol>
        </aside>

        <div className="hist-hero-foot">
          <span>Archiv komunity</span>
          <span className="hist-hero-foot-dot">●</span>
          <span>{chapters.reduce((n, c) => n + c.entries.length, 0)} záznamů</span>
        </div>
      </header>

      <main className="hist-main">
        {chapters.map((chapter, ci) => (
          <section
            key={chapter.year}
            id={`chapter-${chapter.year}`}
            className={`hist-chapter${chapter.closing ? ' hist-chapter-closing' : ''}`}
          >
            <div className="hist-chapter-marker">
              <div className="hist-chapter-sticky">
                <div className="hist-chapter-tag">Kapitola</div>
                <div className="hist-chapter-roman">{chapter.roman}</div>
                <div className="hist-chapter-year">{chapter.year}</div>
                <div className="hist-chapter-words">{chapter.yearWords}</div>
                <div className="hist-chapter-rule" />
                <div className="hist-chapter-sub">{chapter.subtitle}</div>
              </div>
            </div>

            <div className="hist-chapter-feed">
              {chapter.entries.map((entry, ei) => (
                <article
                  key={entry.archive}
                  className={`hist-entry hist-entry-${ei % 2 === 0 ? 'left' : 'right'}${entry.live ? ' hist-entry-live' : ''}`}
                >
                  <header className="hist-entry-head">
                    <span className="hist-entry-arch">
                      Archiv № {entry.archive} / {chapter.year}
                    </span>
                    <span className="hist-entry-season">{entry.season}</span>
                  </header>

                  <div className="hist-entry-tag">
                    <span className="hist-entry-tag-mark">✦</span>
                    {entry.tag}
                  </div>

                  <h3 className="hist-entry-title">{entry.title}</h3>

                  <p className="hist-entry-body">{entry.body}</p>

                  <footer className="hist-entry-foot">
                    <div className="hist-entry-stat">
                      <span className="hist-entry-stat-label">{entry.statLabel}</span>
                      <span className="hist-entry-stat-value">{entry.statValue}</span>
                    </div>
                    {entry.live && <span className="hist-entry-pulse" aria-hidden="true" />}
                  </footer>
                </article>
              ))}
            </div>
          </section>
        ))}

        <div className="hist-coda">
          <div className="hist-coda-stamp">
            <span>Pokračuje</span>
            <span className="hist-coda-stamp-arrow">→</span>
          </div>
          <p className="hist-coda-text">
            Tahle stránka se píše dál.<br />
            Každá akce přidá další záznam do archivu.
          </p>
          <div className="hist-coda-meta">
            <span>End&nbsp;of&nbsp;Vol.&nbsp;01</span>
            <span className="hist-coda-rule" />
            <span>Game&nbsp;of&nbsp;Life&nbsp;©&nbsp;2021—{new Date().getFullYear()}</span>
          </div>
        </div>
      </main>
    </div>
  );
}

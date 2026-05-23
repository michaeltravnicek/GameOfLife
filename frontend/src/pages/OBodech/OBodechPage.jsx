import Button from '../../components/Button/Button';
import './OBodechPage.css';

const pointSources = [
  {
    no: '01',
    title: 'Účast na akcích',
    body: 'Každá akce má svou hodnotu bodů — od ranní jógy po vícedenní výjezd. Body se přepisují automaticky po skončení.',
    tag: 'Hlavní zdroj',
  },
  {
    no: '02',
    title: 'Speciální výzvy',
    body: 'Občasné challenge a tematické úkoly, které ti můžou vystřelit pozici v žebříčku.',
    tag: 'Bonus',
  },
  {
    no: '03',
    title: 'Aktivita v komunitě',
    body: 'Fotky, zpětná vazba, pomoc s organizací — věci, které drží Game of Life při životě.',
    tag: 'Komunita',
  },
];

const valuationCriteria = [
  { label: 'Typ akce', detail: 'Běh, tanec, workshop, výjezd…' },
  { label: 'Délka & intenzita', detail: 'Hodina vs. víkend, lehká vs. tvrdá' },
  { label: 'Obtížnost', detail: 'Kolik tě stojí překonat sám sebe' },
];

const rewardTiers = [
  {
    range: '0 — 100',
    title: 'Začátečník',
    body: 'První kroky. Poznáš lidi, vyzkoušíš formát a najdeš si svůj rytmus.',
    perk: 'Členský status',
  },
  {
    range: '100 — 500',
    title: 'Stálice',
    body: 'Tvoje jméno už komunitě něco říká. Časem otevíráme přístup ke slevám na akce.',
    perk: 'Slevy na vstupné',
    accent: true,
  },
  {
    range: '500 +',
    title: 'Legenda',
    body: 'Top hráči sezóny. Plánujeme exkluzivní benefity, merch a pozvánky.',
    perk: 'Exkluzivní benefity',
  },
];

export default function OBodechPage() {
  return (
    <div className="obodech-page">
      <div className="obo-stage" aria-hidden="true" />
      <div className="obo-grain" aria-hidden="true" />
      <div className="obo-vignette" aria-hidden="true" />

      <header className="obo-hero">
        <div className="obo-hero-meta">
          <span className="obo-hero-vol">Manuál</span>
          <span className="obo-hero-rule" />
          <span className="obo-hero-range">Systém bodů & odměn</span>
        </div>

        <h1 className="obo-hero-title">
          <span className="obo-hero-line obo-hero-line-1">O bo</span>
          <span className="obo-hero-line obo-hero-line-2">dech<span className="obo-hero-mark">*</span></span>
        </h1>

        <p className="obo-hero-tagline">
          Body jsou <em>měřítkem tvého zapojení</em> v Game of Life — odměna za to,
          že přijdeš, vyjdeš z komfortní zóny a žiješ.
        </p>

        <aside className="obo-hero-key" aria-label="Legenda">
          <div className="obo-hero-key-row">
            <span className="obo-hero-key-glyph">✦</span>
            <span className="obo-hero-key-label">Body</span>
            <span className="obo-hero-key-val">aktivita</span>
          </div>
          <div className="obo-hero-key-row">
            <span className="obo-hero-key-glyph">▲</span>
            <span className="obo-hero-key-label">Pozice</span>
            <span className="obo-hero-key-val">leaderboard</span>
          </div>
          <div className="obo-hero-key-row">
            <span className="obo-hero-key-glyph">●</span>
            <span className="obo-hero-key-label">Status</span>
            <span className="obo-hero-key-val">komunita</span>
          </div>
        </aside>

        <div className="obo-hero-foot">
          <span>Verze</span>
          <span className="obo-hero-foot-dot">●</span>
          <span>v 2.0 — Sezóna 2026</span>
        </div>
      </header>

      <main className="obo-main">
        {/* Section 1 — What */}
        <section className="obo-section">
          <div className="obo-section-head">
            <div className="obo-section-num">I</div>
            <div className="obo-section-meta">
              <div className="obo-section-tag">Sekce</div>
              <h2 className="obo-section-title">Co jsou body?</h2>
            </div>
          </div>

          <div className="obo-intro">
            <p className="obo-intro-text">
              Body měří tvoje zapojení v Game of Life. Jsou odměnou za účast na akcích,
              za odvahu jít mimo komfortní zónu a za aktivní angažování se v komunitě.
              Tvůj celkový počet bodů určuje pozici na leaderboardu a ovlivňuje status v partě.
            </p>
            <div className="obo-intro-stat">
              <div className="obo-intro-stat-num">100+</div>
              <div className="obo-intro-stat-label">aktivních hráčů</div>
            </div>
          </div>
        </section>

        {/* Section 2 — How */}
        <section className="obo-section">
          <div className="obo-section-head">
            <div className="obo-section-num">II</div>
            <div className="obo-section-meta">
              <div className="obo-section-tag">Sekce</div>
              <h2 className="obo-section-title">Jak sbírat body</h2>
            </div>
          </div>

          <div className="obo-sources">
            {pointSources.map((s) => (
              <article key={s.no} className="obo-source">
                <div className="obo-source-head">
                  <span className="obo-source-no">№ {s.no}</span>
                  <span className="obo-source-tag">{s.tag}</span>
                </div>
                <h3 className="obo-source-title">{s.title}</h3>
                <p className="obo-source-body">{s.body}</p>
              </article>
            ))}
          </div>

          <div className="obo-valuation">
            <div className="obo-valuation-label">
              <span className="obo-valuation-label-mark">✦</span>
              Hodnota bodů závisí na
            </div>
            <ul className="obo-valuation-list">
              {valuationCriteria.map((v) => (
                <li key={v.label} className="obo-valuation-item">
                  <div className="obo-valuation-key">{v.label}</div>
                  <div className="obo-valuation-val">{v.detail}</div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Section 3 — Rewards */}
        <section className="obo-section">
          <div className="obo-section-head">
            <div className="obo-section-num">III</div>
            <div className="obo-section-meta">
              <div className="obo-section-tag">Sekce</div>
              <h2 className="obo-section-title">Odměny a výhody</h2>
            </div>
          </div>

          <p className="obo-section-lead">
            Game of Life vyvíjí systém odměn propojený s pozicí na leaderboardu.
            Tady je, co plánujeme — a co už dnes funguje.
          </p>

          <div className="obo-tiers">
            {rewardTiers.map((t, i) => (
              <article key={t.range} className={`obo-tier${t.accent ? ' obo-tier-accent' : ''}`}>
                <div className="obo-tier-rk">{['I', 'II', 'III'][i]}</div>
                <div className="obo-tier-range">{t.range} <span>bodů</span></div>
                <h3 className="obo-tier-title">{t.title}</h3>
                <p className="obo-tier-body">{t.body}</p>
                <div className="obo-tier-perk">
                  <span className="obo-tier-perk-mark">→</span>
                  {t.perk}
                </div>
              </article>
            ))}
          </div>

          <div className="obo-cta">
            <div className="obo-cta-stamp">
              <span>Brzy</span>
              <span className="obo-cta-stamp-arrow">→</span>
            </div>
            <p className="obo-cta-text">
              Sleduj naše sociální sítě a web, ať ti neunikly nové informace
              o odměnách a benefitech.
            </p>
            <div className="obo-cta-links">
              <Button variant="cta" size="sm" as="a" href="https://www.instagram.com/gameofyolo" target="_blank" rel="noopener noreferrer">Instagram</Button>
              <Button variant="cta" size="sm" as="a" href="https://www.facebook.com/gameofyolo" target="_blank" rel="noopener noreferrer">Facebook</Button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

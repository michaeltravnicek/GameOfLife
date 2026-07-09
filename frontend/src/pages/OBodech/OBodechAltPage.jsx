import PageHero from '../../components/PageHero/PageHero';
import Reveal from '../../components/Reveal/Reveal';
import Button from '../../components/Button/Button';
import { TicketFrame } from '../../components/DashedBorder/DashedBorder';
import './OBodechAltPage.css';

// PREVIEW — poster-wall redesign of /o-bodech under the print rule set
// (texture wall, cream ticket sources, dark ticket table + rewards, one
// hard-edged photo band). If it wins, this replaces OBodechPage.

const sources = [
  { pts: '+25–250', num: '01', tag: 'Účast', title: 'Akce Game of Life', text: 'Hlavní zdroj bodů. Každá akce má svoji hodnotu — od ranní pětky po vícedenní expedici. Body se připisují za samotnou účast, nepočítá se umístění.' },
  { pts: '+50–500', num: '02', tag: 'Bonus', title: 'Speciální výzvy', text: 'Extra body za vybrané challenges mezi akcemi — solo úkoly, sezónní mise, skryté questy. Vyhlašujeme je nepravidelně, vyplatí se sledovat IG.' },
  { pts: '+10–80', num: '03', tag: 'Komunita', title: 'Aktivita v komunitě', text: 'Body za to, že tu fyzicky držíš věci pohromadě. Pomoc s organizací, přivedený nový hráč, fotka z akce do galerie, ranní příprava ohně.' },
];

const examples = [
  { name: 'Ranní pětka v Lužánkách', sub: '5 km · 1 hod', type: 'sport', typeLabel: 'Sport', diff: '★ ★', pts: 25 },
  { name: 'Dance Class · Karlín', sub: '2 hod · live DJ', type: 'body', typeLabel: 'Tělo', diff: '★ ★ ★', pts: 50 },
  { name: 'Frog Jumps', sub: '18 km na čtyřech', type: 'sport', typeLabel: 'Sport', diff: '★ ★ ★ ★', pts: 50 },
  { name: 'Táborák na náměstí Svobody', sub: '6 hod zpívání + přespání', type: 'game', typeLabel: 'Hra', diff: '★ ★ ★', pts: 80 },
  { name: 'Nahá Míle', sub: '1 609 m · bez triček', type: 'sport', typeLabel: 'Sport', diff: '★ ★ ★ ★ ★', pts: 120 },
  { name: 'C50', sub: '50 km na kole · Brno → Vranov', type: 'sport', typeLabel: 'Sport', diff: '★ ★ ★ ★', pts: 150 },
  { name: 'Sázava splav', sub: '3 dny · 4 jezy · 7 raftů', type: 'game', typeLabel: 'Hra', diff: '★ ★ ★', pts: 250 },
];

const rewards = [
  { ico: '★', title: 'Úrovně podle leaderboardu', text: 'Bronz · Stříbro · Zlato · Legenda. Každá úroveň otevírá vlastní okruh akcí, čepic a vnitřních vtipů, kterým venku nikdo nerozumí.' },
  { ico: '%', title: 'Slevy na vstupné', text: 'Body půjde uplatnit jako slevu na vstupné na placené akce. Čím víc hraješ, tím levnější další hra. Logické.' },
  { ico: '+', title: 'Další výhody', text: 'Přednostní registrace na vyprodané akce, merch se slevou, pozvánky na uzavřené nočky. Detaily upřesníme.' },
];

export default function OBodechAltPage() {
  return (
    <div className="obodechalt-page">
      <PageHero
        eyebrow="Systém bodů"
        title={<>O bodech<br />a cenách</>}
        divider={false}
      />

      <Reveal as="section" stagger className="credits" aria-label="Rozsah bodů">
        <div className="credit">
          <div className="credit-label">— Od —</div>
          <div className="credit-value">+10</div>
          <div className="credit-sub">za fotku v galerii nebo přivedení nového hráče</div>
        </div>
        <div className="credit">
          <div className="credit-label">— Do —</div>
          <div className="credit-value">+250</div>
          <div className="credit-sub">za vícedenní expedici, kdy zvedneš tábor</div>
        </div>
      </Reveal>

      <main className="body">
        <Reveal as="section" className="section">
          <div className="sec-eyebrow">Co jsou body</div>
          <h2 className="sec-heading">Měřítko <span className="pink">zapojení</span>, ne výhry</h2>
          <p className="intro-quote">Body měří, kolik jsi do hry vložil. Jsou odměnou za účast, za odvahu jít mimo komfortní zónu a za to, že jsi prostě přišel.</p>
        </Reveal>

        <Reveal as="section" className="section">
          <div className="sec-eyebrow">Zdroje bodů</div>
          <h2 className="sec-heading">Odkud se <span className="pink">berou</span></h2>
          <div className="sources">
            {sources.map((s) => (
              <article key={s.num} className="source">
                <span className="source-pts">{s.pts}</span>
                <div className="source-num">{s.num}</div>
                <div className="source-tag">{s.tag}</div>
                <h3 className="source-title">{s.title}</h3>
                <p className="source-text">{s.text}</p>
              </article>
            ))}
          </div>
        </Reveal>

        <Reveal as="section" className="section">
          <div className="sec-eyebrow">Příklady</div>
          <h2 className="sec-heading">Kolik za <span className="pink">co</span></h2>
          <p className="intro-quote">Žádný kalkulátor, žádný vzorec. Vojta přiřkne akci hodnotu předem podle toho, jak je dlouhá, náročná a kolik k ní bude potřeba odvahy. Nové typy akcí mají často vyšší ohodnocení.</p>

          <div className="ticket-list">
            <TicketFrame />
            <div className="examples">
              <div className="examples-inner">
                <div className="ex-head">
                  <span>Akce</span>
                  <span className="col-type">Typ</span>
                  <span className="col-diff">Náročnost</span>
                  <span className="col-pts">Body</span>
                </div>
                {examples.map((e) => (
                  <div key={e.name} className="ex-row">
                    <div className="ex-name">{e.name}<span className="s">{e.sub}</span></div>
                    <span className={`ex-pill t-${e.type}`}>{e.typeLabel}</span>
                    <span className="ex-diff">{e.diff}</span>
                    <span className="ex-pts">{e.pts}<span className="u">pts</span></span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
      </main>

      {/* Hard-edged photo band — the page's single photo moment (homepage
          poster-section pattern: light tint, photo stays alive). */}
      <section className="poster-band" aria-label="Pravidlo číslo jedna">
        <div className="pb-bg" />
        <div className="pb-tint" />
        <div className="pb-inner">
          <div className="pb-eyebrow">— Pravidlo č. 1 —</div>
          <h2 className="pb-line">Body se nesbírají od stolu.</h2>
        </div>
      </section>

      <main className="body">
        <Reveal as="section" className="section">
          <div className="sec-eyebrow">Odměny a výhody</div>
          <h2 className="sec-heading">Co za to <span className="pink">jednou bude</span></h2>
          <p className="intro-quote">Reward systém se teď peče. Kromě hřejivého pocitu žádnou fyzickou odměnu zatím nedostaneš. Tady je ale, co plánujeme a na co se můžeš těšit.</p>

          <div className="rewards">
            {rewards.map((r) => (
              <article key={r.title} className="reward">
                <TicketFrame />
                <div className="reward-in">
                  <span className="soon-stamp">★ Brzy</span>
                  <div className="reward-ico">{r.ico}</div>
                  <h3 className="reward-title">{r.title}</h3>
                  <p className="reward-text">{r.text}</p>
                </div>
              </article>
            ))}
          </div>
        </Reveal>

        <section className="obo-cta" aria-label="Sleduj nás">
          <div className="obo-cta-stamp">
            <span>Brzy</span>
            <span className="obo-cta-stamp-arrow">→</span>
          </div>
          <p className="obo-cta-text">Sleduj naše sociální sítě a web, ať ti neunikly nové informace o odměnách a benefitech.</p>
        </section>

        <section className="cta-foot">
          <div className="cta-row">
            <Button as="link" to="/leaderboard" variant="frost" size="lg">← Zpět na leaderboard</Button>
            <Button as="link" to="/events" size="lg">Zobrazit akce <span className="arr" /></Button>
          </div>
        </section>
      </main>
    </div>
  );
}

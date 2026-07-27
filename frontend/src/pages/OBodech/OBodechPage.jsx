import PageHero from '../../components/PageHero/PageHero';
import Reveal from '../../components/Reveal/Reveal';
import Button from '../../components/Button/Button';
import './OBodechPage.css';

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

export default function OBodechPage() {
  return (
    <div className="gol-page obodech-page">
      <div className="stage" aria-hidden="true" />
      <div className="gol-page-grain" aria-hidden="true" />

      <PageHero
        eyebrow="Systém bodů"
        title={<>O bodech<br />a cenách</>}
      />

      <Reveal as="section" stagger className="gol-credits" aria-label="Rozsah bodů">
        <div className="gol-credit">
          <div className="gol-credit-label">— Od —</div>
          <div className="gol-credit-value">+10</div>
          <div className="gol-credit-sub">za fotku v galerii nebo přivedení nového hráče</div>
        </div>
        <div className="gol-credit">
          <div className="gol-credit-label">— Do —</div>
          <div className="gol-credit-value">+250</div>
          <div className="gol-credit-sub">za vícedenní expedici, kdy zvedneš tábor</div>
        </div>
      </Reveal>

      <main className="body">
        <Reveal as="section" className="section">
          <div className="gol-sec-eyebrow sec-eyebrow">Co jsou body</div>
          <h2 className="sec-heading">Měřítko <span className="pink">zapojení</span>, ne výhry</h2>
          <p className="intro-quote">Body měří, kolik jsi do hry vložil. Jsou odměnou za účast, za odvahu jít mimo komfortní zónu a za to, že jsi prostě přišel.</p>
        </Reveal>

        <Reveal as="section" className="section">
          <div className="gol-sec-eyebrow sec-eyebrow">Příklady</div>
          <h2 className="sec-heading">Kolik za <span className="pink">co</span></h2>
          <p className="intro-quote" style={{ marginBottom: 28 }}>Žádný kalkulátor, žádný vzorec. Vojta přiřkne akci hodnotu předem podle toho, jak je dlouhá, náročná a kolik k ní bude potřeba odvahy. Nové typy akcí mají často vyšší ohodnocení.</p>

        </Reveal>

        <Reveal as="section" className="section">
          <div className="gol-sec-eyebrow sec-eyebrow">Odměny a výhody</div>
          <h2 className="sec-heading">Co za to <span className="pink">jednou bude</span></h2>
          <p className="intro-quote" style={{ marginBottom: 30 }}>Reward systém se teď peče. Kromě hřejivého pocitu žádnou fyzickou odměnu zatím nedostaneš. Tady je ale, co plánujeme a na co se můžeš těšit.</p>

          <div className="rewards">
            {rewards.map((r) => (
              <article key={r.title} className="reward">
                <span className="soon-stamp">★ Brzy</span>
                <div className="reward-ico">{r.ico}</div>
                <h3 className="reward-title">{r.title}</h3>
                <p className="reward-text">{r.text}</p>
              </article>
            ))}
          </div>
        </Reveal>
      </main>

      <section className="obo-cta" aria-label="Sleduj nás">
        <div className="obo-cta-stamp">
          <span>Brzy</span>
          <span className="obo-cta-stamp-arrow">→</span>
        </div>
        <p className="obo-cta-text">Sleduj naše sociální sítě a web, ať ti neunikly nové informace o odměnách a benefitech.</p>
      </section>

      <section className="cta-foot">
        <div className="label">— Body se nesbírají od stolu —</div>
        <div className="cta-row">
          <Button as="link" to="/leaderboard" variant="frost" size="lg">← Zpět na leaderboard</Button>
          <Button as="link" to="/events" size="lg">Zobrazit akce <span className="arr" /></Button>
        </div>
      </section>
    </div>
  );
}

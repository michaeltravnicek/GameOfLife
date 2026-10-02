import PageHero from '../../components/PageHero/PageHero';
import PageStage from '../../components/PageStage/PageStage';
import SectionHeader from '../../components/SectionHeader/SectionHeader';
import Stamp from '../../components/Stamp/Stamp';
import Reveal from '../../components/Reveal/Reveal';
import Button from '../../components/Button/Button';
import './OBodechPage.css';

const rewards = [
  { title: 'Úrovně podle leaderboardu', text: 'Bronz · Stříbro · Zlato · Legenda. Každá úroveň otevírá vlastní okruh akcí, čepic a vnitřních vtipů, kterým venku nikdo nerozumí.' },
  { title: 'Slevy na vstupné', text: 'Body půjde uplatnit jako slevu na vstupné na placené akce. Čím víc hraješ, tím levnější další hra. Logické.' },
  { title: 'Další výhody', text: 'Přednostní registrace na vyprodané akce, merch se slevou, pozvánky na uzavřené nočky. Detaily upřesníme.' },
];

export default function OBodechPage() {
  return (
    <div className="obodech-page has-stage">
      {/* Dimmed: a reading page, the darker backdrop keeps the long text calm. */}
      <PageStage image="gal1" position="center 28%" tint="dim" />

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
          <SectionHeader rule={false} onPhoto eyebrow="— Co jsou body —" heading={<>Měřítko <span className="pink">zapojení</span>, ne výhry</>} />
          <p className="gol-quote gol-quote--on-photo">Body měří, kolik jsi do hry vložil. Jsou odměnou za účast, za odvahu jít mimo komfortní zónu a za to, že jsi prostě přišel.</p>
        </Reveal>

        <Reveal as="section" className="section">
          <SectionHeader rule={false} onPhoto eyebrow="— Příklady —" heading={<>Kolik za <span className="pink">co</span></>} />
          <p className="gol-quote gol-quote--on-photo gol-quote--lead">Žádný kalkulátor, žádný vzorec. Vojta přiřkne akci hodnotu předem podle toho, jak je dlouhá, náročná a kolik k ní bude potřeba odvahy. Nové typy akcí mají často vyšší ohodnocení.</p>
        </Reveal>

        <Reveal as="section" className="section">
          <SectionHeader rule={false} onPhoto eyebrow="— Odměny a výhody —" heading={<>Co za to <span className="pink">jednou bude</span></>} />
          <p className="gol-quote gol-quote--on-photo gol-quote--lead">Reward systém se teď peče. Kromě hřejivého pocitu žádnou fyzickou odměnu zatím nedostaneš. Tady je ale, co plánujeme a na co se můžeš těšit.</p>

          <div className="rewards">
            {rewards.map((r) => (
              <article key={r.title} className="gol-card gol-card--lift reward">
                <Stamp tilt={4} className="soon-stamp">★ Brzy</Stamp>
                <h3 className="reward-title">{r.title}</h3>
                <p className="reward-text">{r.text}</p>
              </article>
            ))}
          </div>
        </Reveal>
      </main>

      <section className="obo-cta" aria-label="Sleduj nás">
        <p className="obo-cta-text">Sleduj naše sociální sítě a web, ať ti neunikly nové informace o odměnách a benefitech.</p>
      </section>

      <section className="gol-cta-foot">
        <div className="gol-cta-foot-label">— Body se nesbírají od stolu —</div>
        <div className="gol-cta-foot-row">
          <Button as="link" to="/leaderboard" variant="frost" size="lg">← Zpět na leaderboard</Button>
          <Button as="link" to="/events" size="lg">Zobrazit akce <span className="arr" /></Button>
        </div>
      </section>
    </div>
  );
}

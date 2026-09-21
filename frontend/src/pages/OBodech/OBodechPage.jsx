import { useMemo } from 'react';
import { fetchEvents } from '../../services/api';
import { useCachedQuery } from '../../services/queryCache';
import { CACHE_TTL } from '../../constants/config';
import PageHero from '../../components/PageHero/PageHero';
import PageStage from '../../components/PageStage/PageStage';
import PageState from '../../components/PageState/PageState';
import SectionHeader from '../../components/SectionHeader/SectionHeader';
import StatList from '../../components/StatList/StatList';
import { eventList, EVENT_LIST_CLASS } from '../../components/StatList/eventColumns';
import Reveal from '../../components/Reveal/Reveal';
import Button from '../../components/Button/Button';
import './OBodechPage.css';

// How many past events the "Kolik za co" ladder shows — enough to span the
// +10 … +250 range without turning into a second events page.
const EXAMPLE_COUNT = 6;
// The events endpoint is date-ordered; a page this size covers a full season.
const EXAMPLE_POOL = 120;
const EXAMPLE_COLUMNS = eventList({ include: ['cat', 'info', 'dt', 'pts'] });

const rewards = [
  { ico: '★', title: 'Úrovně podle leaderboardu', text: 'Bronz · Stříbro · Zlato · Legenda. Každá úroveň otevírá vlastní okruh akcí, čepic a vnitřních vtipů, kterým venku nikdo nerozumí.' },
  { ico: '%', title: 'Slevy na vstupné', text: 'Body půjde uplatnit jako slevu na vstupné na placené akce. Čím víc hraješ, tím levnější další hra. Logické.' },
  { ico: '+', title: 'Další výhody', text: 'Přednostní registrace na vyprodané akce, merch se slevou, pozvánky na uzavřené nočky. Detaily upřesníme.' },
];

export default function OBodechPage() {
  // Real events, real points — the best explanation of the scale is the scale
  // itself. Past events only (their points are final), spread from the top of
  // the range to the bottom so the ladder reads as a range, not a top list.
  const { data, loading, error, refetch } = useCachedQuery(
    `events:past|examples|${EXAMPLE_POOL}`,
    () => fetchEvents({ period: 'past', limit: EXAMPLE_POOL }),
    { ttl: CACHE_TTL.EVENTS },
  );
  const examples = useMemo(() => {
    const scored = (data?.events || [])
      .filter((e) => typeof e.points === 'number' && e.points > 0)
      .sort((a, b) => b.points - a.points);
    if (scored.length <= EXAMPLE_COUNT) return scored;
    // Evenly spaced picks across the sorted list: highest, lowest, and steps
    // between, so +250 and +10 both make the cut.
    const step = (scored.length - 1) / (EXAMPLE_COUNT - 1);
    const picks = new Set();
    for (let i = 0; i < EXAMPLE_COUNT; i++) picks.add(Math.round(i * step));
    return [...picks].map((i) => scored[i]);
  }, [data]);

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

          <div className="gol-card gol-card--flush examples">
            {loading && !data ? (
              <PageState kind="loading" compact text="Načítám příklady…" />
            ) : error && !data ? (
              <PageState kind="error" compact text="Příklady se nepodařilo načíst." onRetry={refetch} busy={loading} />
            ) : (
              <StatList
                className={`${EVENT_LIST_CLASS} examples-list`}
                columns={EXAMPLE_COLUMNS.columns}
                gridTemplate={EXAMPLE_COLUMNS.gridTemplate}
                rows={examples}
                rowKey={(e) => e.slug}
                rowLink={(e) => `/events/${e.slug}`}
                rowClass={() => 'past'}
                emptyText="Zatím žádné bodované akce."
              />
            )}
          </div>
        </Reveal>

        <Reveal as="section" className="section">
          <SectionHeader rule={false} onPhoto eyebrow="— Odměny a výhody —" heading={<>Co za to <span className="pink">jednou bude</span></>} />
          <p className="gol-quote gol-quote--on-photo gol-quote--lead">Reward systém se teď peče. Kromě hřejivého pocitu žádnou fyzickou odměnu zatím nedostaneš. Tady je ale, co plánujeme a na co se můžeš těšit.</p>

          <div className="rewards">
            {rewards.map((r) => (
              <article key={r.title} className="gol-card gol-card--lift reward">
                <span className="gol-stamp--gold soon-stamp">★ Brzy</span>
                <div className="reward-ico">{r.ico}</div>
                <h3 className="reward-title">{r.title}</h3>
                <p className="reward-text">{r.text}</p>
              </article>
            ))}
          </div>
        </Reveal>
      </main>

      <section className="obo-cta" aria-label="Sleduj nás">
        <div className="gol-stamp">
          <span>Brzy</span>
          <span className="gol-stamp-arrow">→</span>
        </div>
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

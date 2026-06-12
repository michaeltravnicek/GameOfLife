import PageHero from '../../components/PageHero/PageHero';
import Reveal from '../../components/Reveal/Reveal';
import Button from '../../components/Button/Button';
import './HistoriePage.css';

const credits = [
  { label: '— Rok 0 —', value: '2024', sub: 'První ročník' },
  { label: '— Akcí —', value: '42', sub: 'a počítáme dál' },
  { label: '— Hráčů —', value: '250+', sub: 'z Brna i odjinud' },
  { label: '— Bodů —', value: '25K', sub: 'rozdáno do žebříčku' },
];

const years = [
  {
    year: '2026',
    muted: false,
    rows: [
      {
        side: 'left', type: 'photo', img: '/img/gal0.webp', first: '★ Poprvé', date: '12. 05. 2026', pts: '+50 pts', evStamp: '/img/GOL_FrogJumps_transparent.webp',
        tag: 'Nová disciplína · Brno', title: 'Frog Jumps',
        text: 'První ročník žabích skoků kolem celé Brněnské přehrady. 18 km na čtyřech, bahno za uši, večer pivo a omluvy. Nikdo nečekal, že to bude tak vyčerpávající.',
        chips: [{ label: '📍 Bystrc' }, { label: '⏱ 4h 12min' }, { label: '★ 38 hráčů', attended: true }],
      },
      {
        side: 'right', type: 'note', noteDate: '15. 05. 2026 · Milník', title: 'Hráč číslo 250',
        text: <>Tři dny po Frog Jumps se přidává <strong>Eliška z Olomouce</strong> — a tím překračujeme symbolickou hranici 250 aktivních hráčů. Z hospodského žertu v roce 2022 je teď komunita o velikosti malé vesnice.</>,
      },
      {
        side: 'left', type: 'photo', img: '/img/gal3.webp', first: '★ Poprvé v PRAZE', date: '18. 05. 2026', pts: '+50 pts', evStamp: '/img/GOL_Dance_transparent.webp',
        tag: 'Tělo · Praha', title: 'Dance Class',
        text: 'První pražská taneční hodina. 47 lidí v Karlíně, dvě hodiny, žádné zrcadlo — jenom hudba a stěna. Tím se Game of Life oficiálně přesouvá za hranice Brna.',
        chips: [{ label: '📍 Karlín' }, { label: '🎵 Live DJ' }, { label: '★ 47 hráčů', attended: true }],
      },
    ],
  },
  {
    year: '2025',
    muted: true,
    rows: [
      {
        side: 'right', type: 'photo', muted: true, img: '/img/gal2.webp', first: '★ Poprvé na náměstí', date: '14. 09. 2025', pts: '+80 pts',
        tag: 'Legenda · Brno', title: 'Táborák na náměstí Svobody',
        text: 'Vůbec první oheň, který jsme zapálili přímo na náměstí — bez povolení, ale s úsměvem. Kytary, kouř a zpívání do tří do rána. Po akci jsme přespávali na dlažbě v dekách. Strážníci jen kroutili hlavou.',
        chips: [{ label: '📍 Náměstí Svobody' }, { label: '🔥 6h zpívání' }, { label: '★ 64 hráčů', attended: true }],
      },
      {
        side: 'left', type: 'note', noteDate: '01. 08. 2025 · Nový rituál', title: 'Spustili jsme leaderboard',
        text: <>Konec Excelu. Po dvou letech ručního počítání bodů spouštíme veřejný žebříček. <em>„Hlavně to nepoužívejte vážně,“</em> zní oficiální motto. Pak Toman s Müllerem hodinu vyšetřují, kdo má víc bodů.</>,
      },
      {
        side: 'right', type: 'photo', muted: true, img: '/img/gal1.webp', date: '28. 06. 2025', pts: '+120 pts',
        tag: 'Výzva · Brno', title: 'Nahá Míle',
        text: '1 609 metrů. Bez triček, bez výmluv. Druhý ročník — letos i v dešti. Vyhrál Toman v 5:42, ale fakt na tom nezáleží.',
        chips: [{ label: '📍 Lužánky' }, { label: '🌧 9 °C' }, { label: '★ 22 hráčů', attended: true }],
      },
      {
        side: 'left', type: 'photo', muted: true, img: '/img/gal0.webp', first: '★ Poprvé na vodě', date: '11. 04. 2025', pts: '+40 pts',
        tag: 'Voda · Vysočina', title: 'Sázava Splav',
        text: 'První vícedenní vodácká výprava komunity. Tři dny, čtyři jezy, sedm raftů. Jeden převrácený, dva ztracené pádla, nula utopených.',
        chips: [{ label: '📍 Sázava' }, { label: '🛶 3 dny' }, { label: '★ 31 hráčů', attended: true }],
      },
    ],
  },
  {
    year: '2024',
    muted: true,
    rows: [
      {
        side: 'right', type: 'photo', muted: true, img: '/img/gal3.webp', first: '★ Poprvé', date: '07. 09. 2024', pts: '+150 pts', evStamp: '/img/GOL_C50_transparent.webp',
        tag: 'Kolo · Brno', title: 'První C50',
        text: 'Padesát kilometrů na kole, prvních dvacet hráčů, sedmnáct dojelo. Zrodila se tradice, která teď táhne celý kalendář — a do roka přibyla C100.',
        chips: [{ label: '📍 Brno → Vranov' }, { label: '🚴 50 km' }, { label: '★ 20 hráčů', attended: true }],
      },
      {
        side: 'left', type: 'note', noteDate: 'Léto 2024 · Manifest', title: 'Život je hra. Tak ho hrej.',
        text: <>Na pivním tácku vzniká věta, která se později stane sloganem celé komunity. Napsal ji <strong>Vojta Toman</strong> mezi třetím a čtvrtým pivem. Ráno ji nechtěl ani uznat — ale tácek se zachoval.</>,
      },
      {
        side: 'right', type: 'photo', muted: true, img: '/img/gal2.webp', first: '★ Poprvé v noci', date: '22. 06. 2024', pts: '+60 pts',
        tag: 'Hra · Brno', title: 'Noční bojovka v Lužánkách',
        text: 'První večerní akce vůbec. Čtyři týmy, baterky, šifry vyryté do stromů. Vyhráli ti, co se nechali ztratit nejdéle. Od té doby je nocí v kalendáři víc než dnů.',
        chips: [{ label: '📍 Lužánky' }, { label: '🌙 23:00 → 04:00' }, { label: '★ 28 hráčů', attended: true }],
      },
      {
        side: 'left', type: 'photo', muted: true, img: '/img/gal1.webp', date: '15. 02. 2024', pts: '+30 pts',
        tag: 'Mráz · Krkonoše', title: 'Zimní výstup na Sněžku',
        text: <>−14 °C, vítr 60 km/h, žádné lyže. Vystoupali jsme všichni, sestoupili jsme jen někteří (zbytek lanovkou). Den, kdy se zrodilo pravidlo: <em>kdo dojde, dostane bod navíc.</em></>,
        chips: [{ label: '📍 Krkonoše' }, { label: '🥶 −14 °C' }, { label: '★ 14 hráčů', attended: true }],
      },
      {
        side: 'right', type: 'note', noteDate: 'Leden 2024 · Rok 0', title: 'Začalo to v hospodě',
        text: <>Vojta a Lukáš v hospodě U Kubišty vysloví větu: <em>„Co kdyby měl život vlastní body?“</em> Načrtnou na pivní tácek první pravidla — výzvy, žebříček, táboráky. Mělo to zůstat jen vtip.<br /><br /><strong>Nezůstalo.</strong></>,
      },
    ],
  },
];

function PhotoCard({ row }) {
  return (
    <div className={`card${row.muted ? ' muted' : ''}`}>
      <div className="card-media" style={{ backgroundImage: `url('${row.img}')` }}>
        {row.first && <span className="first-stamp">{row.first}</span>}
        <span className="date-stamp">{row.date}</span>
        <span className="pts-badge">{row.pts}</span>
        {row.evStamp && <img className="ev-stamp" src={row.evStamp} alt="" />}
      </div>
      <div className="card-body">
        <div className="card-tag">{row.tag}</div>
        <h3 className="card-title">{row.title}</h3>
        <p className="card-text">{row.text}</p>
        <div className="card-meta">
          {row.chips.map((c) => (
            <span key={c.label} className={`chip${c.attended ? ' attended' : ''}`}>{c.label}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function NoteCard({ row }) {
  return (
    <div className="card note">
      <span className="note-mark">&ldquo;</span>
      <div className="card-body">
        <div className="note-date">{row.noteDate}</div>
        <h3 className="card-title">{row.title}</h3>
        <p className="card-text">{row.text}</p>
      </div>
    </div>
  );
}

export default function HistoriePage() {
  return (
    <div className="historie-page">
      <div className="stage" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />

      <PageHero
        eyebrow="Co se stalo"
        title="Historie"
        tagline="Každý táborák, každá míle, každý společný večer. Tady je naše paměť — kronika všeho, co se nedá smazat."
      />

      <Reveal as="section" stagger className="credits" aria-label="Souhrn">
        {credits.map((c) => (
          <div key={c.label} className="credit">
            <div className="credit-label">{c.label}</div>
            <div className="credit-value">{c.value}</div>
            <div className="credit-sub">{c.sub}</div>
          </div>
        ))}
      </Reveal>

      <main className="timeline">
        {years.map((y) => (
          <div key={y.year}>
            <div className={`year-mark${y.muted ? ' muted' : ''}`}><span className="y">{y.year}</span></div>
            <Reveal stagger className="spine">
              {y.rows.map((row, i) => (
                <article key={`${y.year}-${i}`} className={`row ${row.side}`}>
                  {row.side === 'right' && <div className="node"><div className="node-dot" /></div>}
                  {row.type === 'photo' ? <PhotoCard row={row} /> : <NoteCard row={row} />}
                  {row.side === 'left' && <div className="node"><div className="node-dot" /></div>}
                </article>
              ))}
            </Reveal>
          </div>
        ))}
      </main>

      <div className="hist-coda">
        <div className="hist-coda-stamp">
          <span>Pokračuje</span>
          <span className="hist-coda-stamp-arrow">→</span>
        </div>
      </div>

      <section className="cta-foot">
        <div className="label">— A teď je řada na tobě —</div>
        <Button as="link" to="/akce" size="lg">Zobrazit nadcházející akce <span className="arr" /></Button>
      </section>
    </div>
  );
}

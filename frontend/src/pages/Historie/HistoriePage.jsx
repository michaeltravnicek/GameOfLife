import { QRCodeSVG } from 'qrcode.react';
import PageHero from '../../components/PageHero/PageHero';
import Reveal from '../../components/Reveal/Reveal';
import Button from '../../components/Button/Button';
import './HistoriePage.css';

// Support QR: the whole block only renders when this env var holds a value
// (a donation link / QR-platba string). Leave it unset to hide the section.
const SUPPORT_QR = import.meta.env.VITE_SUPPORT_QR;

const credits = [
  { label: '— Rok 0 —', value: '2025', sub: 'První ročník' },
  { label: '— Akcí —', value: '70+', sub: 'a počítáme dál' },
  { label: '— Hráčů —', value: '300+', sub: 'z Brna i odjinud' },
  { label: '— Bodů —', value: '30K+', sub: 'rozdáno do žebříčku' },
];

const years = [
  {
    year: '2026',
    muted: false,
    rows: [
      {
        side: 'left', type: 'note', noteDate: '15. 05. 2026 · Milník', title: 'Web Game of Life',
        text: <>Každý z vás si zažil odkaz na whatsupp na instagramu. Bylo to jak jsme po dlouhou dobu fungovali, ale s přibývajícími akcemi a lidmi 
        nás tenhle přístup začal limitovat. Rozhodli jsme se vytvořit web, kde si každý může udělat svůj profil, sledovat žebříček a přidávat se na akce.
        </>,
      },
      {
        side: 'right', type: 'photo', muted: true, img: '/img/gal2.webp', first: '★ Tour', date: '14. 09. 2025', pts: '+50 pts',
        tag: 'Legenda · Česká republika', title: 'Karaoke Tour 2026',
        text: 'Už první rok to bylo super a tento rok ještě lepší. Českou pařitelnou jsme nabírali lidi, dopoledne dělali výlety a večer zpívali do zbláznění.',
        chips: [{ label: '🔥 6h zpívání' }, { label: 'spaní pod hvězdami', attended: true }],
      },
      {
        side: 'left', type: 'note', noteDate: '15. 05. 2026 · Milník', title: 'Česká spořitelna',
        text: <>K naši cestě se přidává cenný partner, někdo kdo nám pomůže realizovat všechny ty blaznívý nápady, na které doteď nebyly prostředky. 
        Tohle parnerství nás hodně posunulo, protože můžeme dělat co nás baví a pro vás akce stále zadarmo.
        </>,
      },
      {
        side: 'right', type: 'photo', muted: true, img: '/img/gal2.webp', first: '★ Výlet', date: '13. 01. 2026', pts: '+0 pts',
        tag: 'Legenda · Česká republika', title: 'Lysá hora 2026',
        text: 'Pro úzkou skupinku lidí jsme vymysleli výlet a společnou chatu. Akce nemusely být jen na jedno odpoledne nebo večer, ale mohli jsme si spolu užít i víc dní.',
        chips: [{ label: '🔥 6h zpívání' }, { label: 'spaní pod hvězdami', attended: true }],
      },
    ],
  },
  {
    year: '2025',
    muted: true,
    rows: [

      
      {
        side: 'left', type: 'photo', muted: true, img: '/img/gal2.webp', first: '★ První tour', date: '14. 09. 2025', pts: '+80 pts',
        tag: 'Legenda · Česká republika', title: 'Karaoke Tour 2025',
        text: 'Už první rok jsme pobrali něco málo techniky a jezdili po republice, kde jste s k nám přidávali a bavili se. Nebyl jsem v tom sám, semnou jezdili v autech i další lidech a prostě bylo to crazy, díky moc',
        chips: [{ label: '🔥 6h zpívání' }, { label: 'spaní pod hvězdami', attended: true }],
      },
      {
        side: 'right', type: 'note', noteDate: '01. 08. 2025 · Nový rituál', title: 'Začátky Game of Life',
        text: <>Už od začátku to bylo o zážitcích, něco co jen tak nezažiješ. Místo, kde získáš odvahu vzít mikrofon do ruky, 
        zatančíš si na ulici a prostě utečeš z každodenního stereotypu. Lidé se bavili, seznamovali ale u toho jsme neskončili, naše
        komunita rostla dál. </>,
      },
      {
        side: 'left', type: 'photo', muted: true, img: '/img/gal0.webp', first: '★ První karaoke', date: '12. 02. 2025', pts: '+40 pts',
        tag: 'Karaoke', title: 'Táborak na náměstí',
        text: 'První karaoke na náměstí, první velká akce. Od tohohle dne se z karaoke stala naše signature akce.',
        chips: [{ label: '📍 Brno' }],
      },
      {
        side: 'right', type: 'note', noteDate: '01. 08. 2025 · Nový rituál', title: 'Začátky Game of Life',
        text: <>Akce pokračovaly většinou v skromném počtu, ale lidé se přidávali a bavilo je to. 
        Zkoušeli jsme nové věci, první achievements, stavění špagetové věže, městečko palermo. 
        Byly to věci, které bylo super s někým sdílet a tady jsem si řekl, že tohle dává smysl. </>,
      },
      {
        side: 'left', type: 'photo', muted: true, img: '/img/gal0.webp', first: '★ První akce', date: '12. 02. 2025', pts: '+40 pts',
        tag: 'Nahá Míle', title: 'Náhá Míle 2025',
        text: 'První nahá míle a první akce Game of Life. Běh městem ve spodním prádle nebo v plavkách',
        chips: [{ label: '📍 Brno' }],
      },
    ],
  }
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
    <div className="gol-page historie-page">
      <div className="stage" aria-hidden="true" />
      <div className="gol-page-grain" aria-hidden="true" />

      <PageHero
        eyebrow="Nostalgické momenty"
        title="Historie"
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
            <div className={`gol-flank year-mark${y.muted ? ' muted' : ''}`}><span className="y">{y.year}</span></div>
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
        <Button as="link" to="/events" size="lg">Zobrazit nadcházející akce <span className="arr" /></Button>
      </section>

      {SUPPORT_QR && (
        <Reveal as="section" className="hist-support" aria-label="Podpoř Game of Life">
          <div className="hist-support-card">
            <div className="hist-support-qr">
              <QRCodeSVG value={SUPPORT_QR} size={196} bgColor="#fff1d4" fgColor="#1a0f0a" level="M" marginSize={2} />
            </div>
            <div className="hist-support-body">
              <div className="hist-support-eyebrow">— Podpoř Game of Life —</div>
              <p className="hist-support-text">
                Gameofyolo žije jen díky vám, díky tomu že se zajímáte a chodíte na akce.
                Připravovat akce nám ale bere hodně úsilí, pokud si i vy ceníte, co pro Vás
                děláme, podpořte gameofyolo přes QR kód a na příští akci si vyzvedněte
                odznáček za odměnu.
              </p>
              <div className="hist-support-reward">
                <img src="/img/gg-pin-gold.svg" alt="" aria-hidden="true" />
                <span>Odznáček za odměnu na příští akci</span>
              </div>
            </div>
          </div>
        </Reveal>
      )}
    </div>
  );
}

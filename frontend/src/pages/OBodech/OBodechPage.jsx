import './OBodechPage.css';

export default function OBodechPage() {
  return (
    <div className="obodech-page">
      <div className="stage" />
      <div className="grain" />

      <header className="hero">
        <div className="eyebrow">Systém bodů</div>
        <h1>O bodech a cenách</h1>
        <p className="tagline">Body jsou měřítkem tvého zapojení do Game of Life a odrážejí tvoji aktivitu v komunině.</p>
        <div className="divider" />
      </header>

      <main className="content-main">
        <div className="info-section">
          <div className="section-title">Co jsou body?</div>
          <div className="info-card">
            <div className="card-text">
              Body měří tvoje zapojení v Game of Life. Jsou odměnou za účast na akcích, za odvahu jít mimo komfortní
              zónu a za aktivní angažování se v komunitě. Tvoj celkový počet bodů určuje tvou pozici na leaderboardu
              a ovlivňuje tvůj status v komunině.
            </div>
          </div>
        </div>

        <div className="info-section">
          <div className="section-title">Jak sbírat body</div>
          <div className="info-card">
            <div className="card-heading">Zdroje bodů</div>
            <ul className="points-list">
              <li>Účast na akcích Game of Life — každá akce má svou hodnotu bodů na základě obtížnosti a typu</li>
              <li>Speciální výzvy a challenges — extra body za vybrané úkoly</li>
              <li>Aktivita v komunitě — zapojení a přispívání do komunity</li>
            </ul>
          </div>
          <div className="info-card">
            <div className="card-heading">Bodový systém</div>
            <div className="card-text">Každá akce má přiřazenu hodnotu bodů na základě:</div>
            <ul className="points-list">
              <li>Typu akce (běh, tanec, workshop atd.)</li>
              <li>Délky a intenzity akce</li>
              <li>Obtížnosti a náročnosti výzvy</li>
            </ul>
          </div>
        </div>

        <div className="info-section">
          <div className="section-title">Odměny a výhody</div>
          <div className="info-card">
            <div className="card-heading">Reward systém</div>
            <div className="card-text">Game of Life vyvíjí systém odměn propojený s tvou pozicí na leaderboardu. Plánujeme zavést:</div>
            <ul className="points-list">
              <li>Více úrovní odměn odpovídajících tvému umístění na leaderboardu</li>
              <li>Využití bodů na slevy na vstupné na akce</li>
              <li>Další výhody a benefity v budoucnosti</li>
            </ul>
            <div className="cta-section">
              <p className="cta-text">Sleduj naše sociální sítě a web, aby ti neunikly nové informace o odměnách a benefitech!</p>
              <div className="cta-links">
                <a href="#" className="cta-link">Instagram</a>
                <a href="#" className="cta-link">Facebook</a>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

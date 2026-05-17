import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchHome } from '../../services/api';
import EventCard from '../../components/EventCard/EventCard';
import Avatar from '../../components/Avatar/Avatar';
import { fmtDate } from '../../utils/date';
import './HomePage.css';

const FALLBACK_GAL = ['/gallery/gal0.jpg', '/gallery/gal1.jpg', '/gallery/gal2.jpg', '/gallery/gal3.jpg'];

export default function HomePage() {
  const [data, setData] = useState({ hero_events: [], upcoming_events: [], top_players: [], about_stats: {} });
  const [slide, setSlide] = useState(0);
  const [galCur, setGalCur] = useState(0);

  useEffect(() => {
    fetchHome().then(setData).catch(() => {});
  }, []);

  const slides = data.hero_events.length
    ? data.hero_events
    : FALLBACK_GAL.map((url, i) => ({ url, name: '', slug: '', date: null, _i: i }));

  useEffect(() => {
    if (slides.length < 2) return;
    const t = setInterval(() => setSlide((c) => (c + 1) % slides.length), 5000);
    return () => clearInterval(t);
  }, [slides.length]);

  const galImages = data.hero_events.length
    ? data.hero_events.map((h) => h.url)
    : FALLBACK_GAL;
  const galN = galImages.length;
  const galPrev = () => setGalCur((c) => (c - 1 + galN) % galN);
  const galNext = () => setGalCur((c) => (c + 1) % galN);

  const stats = data.about_stats || {};

  return (
    <div className="home-page">

      {/* HERO */}
      <section className="hero">
        <div className="hero-slides">
          {slides.map((s, i) => (
            <div
              key={s.slug || String(s._i ?? i)}
              className={`hero-slide${i === slide ? ' active' : ''}`}
              style={{ backgroundImage: `url('${s.url}')` }}
            />
          ))}
        </div>
        <div className="hero-overlay" />
        <div className="hero-inner">
          <div className="hero-eyebrow">— Sezóna 2026 —</div>
          <h1 className="hero-title">{slides[slide]?.name || 'Game of Life'}</h1>
          {slides[slide]?.date && <p className="hero-date">{fmtDate(slides[slide].date)}</p>}
        </div>
        <Link to="/akce" className="btn-pill hero-cta">Zobrazit akce <span className="arr"></span></Link>
        <div className="hero-dots">
          {slides.map((s, i) => (
            <span
              key={s.slug || String(s._i ?? i)}
              role="button"
              aria-label={`Slide ${i + 1}`}
              aria-pressed={i === slide}
              tabIndex={0}
              className={`hero-dot${i === slide ? ' active' : ''}`}
              onClick={() => setSlide(i)}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setSlide(i)}
            />
          ))}
        </div>
      </section>

      {/* UPCOMING EVENTS */}
      <section className="events-section">
        <h2 className="sec-title"><span className="star">✦</span> Nadcházející akce <span className="star">✦</span></h2>
        <div className="events-grid">
          {data.upcoming_events.length === 0 && (
            <p style={{ gridColumn: '1/-1', textAlign: 'center', color: 'rgba(255,255,255,.6)', fontStyle: 'italic' }}>
              Žádné nadcházející akce. Sleduj nás na sítích!
            </p>
          )}
          {data.upcoming_events.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </div>
      </section>

      {/* LEADERBOARD */}
      <section className="lb-section">
        <div className="lb-bg" />
        <div className="lb-tint" />
        <div className="lb-inner">
          <h2 className="lb-title"><span className="tr">🏆</span> Top hráči <span className="tr">🏆</span></h2>
          <div className="lb-card">
            <div className="lb-head"><div>#</div><div>hráč</div><div style={{ textAlign: 'right' }}>pts</div></div>
            {data.top_players.map((p) => {
              const trophyMap = { 1: '🏆', 2: '🥈', 3: '🥉' };
              const isTop = p.rank <= 3;
              const link = p.profile_username ? `/profil/${p.profile_username}` : null;
              const Row = link ? Link : 'div';
              return (
                <Row
                  key={p.id}
                  to={link || undefined}
                  className="lb-row"
                  style={link ? { textDecoration: 'none', color: 'inherit' } : undefined}
                >
                  <span className={`lb-rank${isTop ? ' top' : ''}`}>
                    {trophyMap[p.rank] || `${p.rank}.`}
                  </span>
                  <div className="lb-name"><Avatar name={p.name} size="xs" className="lb-av" />{p.name}</div>
                  <div className="lb-pts">{p.total_points}</div>
                </Row>
              );
            })}
          </div>
        </div>
      </section>

      {/* ABOUT */}
      <section className="about-section">
        <div className="about-inner">
          <div className="about-photo">
            <img src="/gallery/gal3.jpg" alt="Game of Life komunita" loading="lazy" />
          </div>
          <div className="about-content">
            <div className="about-eyebrow">— O nás —</div>
            <h3 className="about-heading">Komunita, která hraje život naplno</h3>
            <p className="about-body">
              <strong>Game of Life</strong> je celoroční komunitní hra plná zábavy, výzev a nezapomenutelných
              zážitků. Vzešla z přesvědčení, že nejlepší okamžiky nevznikají samy — ale když se správní
              lidé potkají ve správný čas.
            </p>
            <p className="about-body">
              Každý event je bodovaný. Každá výzva tě posune dál. Nejde jen o body — jde o přátelství,
              vzpomínky a odvahu vyzkoušet něco nového.
            </p>
            <div className="stats-row">
              <div className="stat-item"><div className="stat-num">{stats.players ?? '—'}</div><div className="stat-label">Hráčů</div></div>
              <div className="stat-item"><div className="stat-num">{stats.events ?? '—'}</div><div className="stat-label">Events</div></div>
              <div className="stat-item"><div className="stat-num">{stats.points ?? '—'}</div><div className="stat-label">Bodů</div></div>
            </div>
            <div style={{ textAlign: 'center', marginTop: '8px' }}>
              <Link to="/historie" className="btn-pill">Číst historii <span className="arr"></span></Link>
            </div>
          </div>
        </div>
      </section>

      {/* GALLERY */}
      <section className="gallery-section">
        <div className="gal-header">
          <h2 className="gal-title"><span className="gal-star">📷</span> Galerie <span className="gal-star">📷</span></h2>
        </div>
        <div className="gal-container">
          <div
            className="gal-side"
            onClick={galPrev}
            style={{ backgroundImage: `url('${galImages[(galCur - 1 + galN) % galN]}')` }}
          />
          <div className="gal-main" style={{ backgroundImage: `url('${galImages[galCur]}')` }} />
          <div
            className="gal-side"
            onClick={galNext}
            style={{ backgroundImage: `url('${galImages[(galCur + 1) % galN]}')` }}
          />
        </div>
        <div className="gal-footer">
          <Link to="/galerie" className="btn-pill">Celá galerie <span className="arr"></span></Link>
        </div>
      </section>

    </div>
  );
}

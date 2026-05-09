import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchEvents } from '../../services/api';
import './EventsPage.css';

const MONTHS = ['ledna', 'února', 'března', 'dubna', 'května', 'června', 'července', 'srpna', 'září', 'října', 'listopadu', 'prosince'];
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getDate()}. ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function EventCard({ ev }) {
  return (
    <Link className={`ev-card${ev.is_past ? ' past' : ''}`} to={`/akce/${ev.slug}`}>
      <span className={`ev-status${ev.is_past ? ' done' : ''}`}>{ev.is_past ? 'Proběhlo' : 'Akce'}</span>
      {ev.image && <img className="ev-badge" src={ev.image} alt="" />}
      <div className="ev-content">
        <h3 className="ev-title">{ev.name}</h3>
        {ev.description && <p className="ev-desc">{ev.description}</p>}
        <div className="ev-meta">
          <div>📅 {fmtDate(ev.date)}</div>
          <div>📍 {ev.place}</div>
        </div>
        <div className="ev-footer">
          <span className="ev-pts">+{ev.points} pts</span>
          <span className="ev-detail">Detail eventu →</span>
        </div>
      </div>
    </Link>
  );
}

export default function EventsPage() {
  const [tab, setTab] = useState('upcoming');
  const [city, setCity] = useState('Vše');
  const [query, setQuery] = useState('');
  const [events, setEvents] = useState([]);
  const [cities, setCities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchEvents()
      .then((d) => {
        setEvents(d.events || []);
        setCities(d.cities || []);
      })
      .finally(() => setLoading(false));
  }, []);

  const cityChoices = useMemo(() => ['Vše', ...cities.map((c) => c.name)], [cities]);

  const { upcoming, past } = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = events.filter((ev) => {
      if (tab === 'upcoming' && ev.is_past) return false;
      if (tab === 'past' && !ev.is_past) return false;
      if (city !== 'Vše' && ev.place !== city) return false;
      if (q && !`${ev.name} ${ev.description} ${ev.place}`.toLowerCase().includes(q)) return false;
      return true;
    });
    return {
      upcoming: filtered.filter((ev) => !ev.is_past).sort((a, b) => new Date(a.date) - new Date(b.date)),
      past: filtered.filter((ev) => ev.is_past).sort((a, b) => new Date(b.date) - new Date(a.date)),
    };
  }, [events, tab, city, query]);

  const empty = !loading && upcoming.length === 0 && past.length === 0;

  return (
    <div className="events-page">
      <div className="stage" />
      <div className="grain" />

      <header className="hero">
        <div className="eyebrow">Kalendář · Sezóna 2025/26</div>
        <h1>Events</h1>
        <p className="tagline">Kompletní seznam akcí. Sbírej body, hraj život.</p>
        <div className="divider" />
      </header>

      <section className="controls">
        <div className="tabs">
          {['upcoming', 'past', 'all'].map((t) => (
            <button key={t} className={`tab${tab === t ? ' on' : ''}`} onClick={() => setTab(t)}>
              {t === 'upcoming' ? 'Nadcházející' : t === 'past' ? 'Proběhlo' : 'Vše'}
            </button>
          ))}
        </div>
        <div className="search">
          <input
            type="text"
            placeholder="Hledat akci…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoComplete="off"
          />
        </div>
      </section>

      <section className="locations">
        {cityChoices.map((c) => (
          <button key={c} className={`loc${city === c ? ' on' : ''}`} onClick={() => setCity(c)}>
            {c}
          </button>
        ))}
      </section>

      <main className="events-main">
        {loading && <div className="empty">Načítám akce…</div>}
        {empty && <div className="empty">Žádné akce nenalezeny.</div>}
        {upcoming.length > 0 && (
          <>
            <div className="group-label">Nadcházející</div>
            <div className="events-grid">
              {upcoming.map((ev) => <EventCard key={ev.id} ev={ev} />)}
            </div>
          </>
        )}
        {past.length > 0 && (
          <>
            <div className="group-label past">Proběhlo</div>
            <div className="events-grid">
              {past.map((ev) => <EventCard key={ev.id} ev={ev} />)}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

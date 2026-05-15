import { useEffect, useMemo, useState } from 'react';
import { fetchEvents } from '../../services/api';
import EventCard from '../../components/EventCard/EventCard';
import TabBar from '../../components/TabBar/TabBar';
import SearchInput from '../../components/SearchInput/SearchInput';
import './EventsPage.css';

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
        <p className="tagline">Kompletní seznam akcí. Od karaoke přes nahou míli, deskovky až po bruslení. Sbírej body, hraj život.</p>
        <div className="divider" />
      </header>

      <section className="controls">
        <TabBar
          tabs={[
            { key: 'upcoming', label: 'Nadcházející' },
            { key: 'past', label: 'Proběhlo' },
            { key: 'all', label: 'Vše' },
          ]}
          active={tab}
          onChange={setTab}
        />
        <SearchInput
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Hledat akci…"
        />
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
              {upcoming.map((ev) => <EventCard key={ev.id} event={ev} theme="light" />)}
            </div>
          </>
        )}
        {past.length > 0 && (
          <>
            <div className="group-label past">Proběhlo</div>
            <div className="events-grid">
              {past.map((ev) => <EventCard key={ev.id} event={ev} theme="light" />)}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createEvent, fetchCategories, fetchBadges } from '../../services/api';
import { extractApiError, reportError } from '../../services/errors';
import { useEventForm, buildEventFormData } from './eventForm';
import EventFormSections from './EventFormSections';
import './EventPage.css';

export default function CreateEventPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [badges, setBadges] = useState([]);
  const {
    form, setForm, categories, allCategories, setAllCategories,
    dirty, saving, setSaving, saveError, setSaveError,
    markDirty, setField, handleCategories, poster,
  } = useEventForm();

  useEffect(() => {
    // Badges are the logo picker's options, so they gate the form the same way
    // categories do — load both before showing it.
    Promise.all([fetchCategories(), fetchBadges()])
      .then(([cats, badgeData]) => {
        if (cats?.categories) setAllCategories(cats.categories);
        if (badgeData?.badges) setBadges(badgeData.badges);
        setLoading(false);
      })
      .catch((err) => {
        reportError('Nepodařilo se načíst kategorie a odznaky.', err);
        setLoading(false);
      });
  }, [setAllCategories]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const formData = buildEventFormData(form, { poster, allCategories, categories });
      const event = await createEvent(formData);
      navigate(`/events/${event.slug}`);
    } catch (err) {
      setSaveError(extractApiError(err, 'Chyba při vytváření akce.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="event-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítání…</div></div>;
  }

  return (
    <div className="event-page">
      <div className="ev-stage" aria-hidden="true" />
      <div className="ev-grain" aria-hidden="true" />

      <section className="ev-head">
        <div className="ev-crumb">— <Link to="/events">Akce</Link> · Vytvořit —</div>
        <div className="ev-eyebrow">Nová akce</div>
        <h1>Vytvořit akci</h1>
      </section>

      <main className="ev-main">
        <EventFormSections
          form={form}
          setForm={setForm}
          setField={setField}
          markDirty={markDirty}
          poster={poster}
          badges={badges}
          allCategories={allCategories}
          categories={categories}
          onCategories={handleCategories}
        />
      </main>

      <section className="ev-commit-zone">
        <div className="ev-commit-label">— Hotovo? —</div>
        <h2>Vytvořit akci</h2>
        <div className="ev-commit-row">
          <Link className="gol-btn ghost" to="/events">Zrušit</Link>
          <button type="button" className="gol-btn primary lg" onClick={handleSave} disabled={saving}>{saving ? 'Vytvářím…' : 'Vytvořit akci'}</button>
        </div>
        <div className="ev-commit-note">{saveError ? `— Chyba: ${saveError} —` : (dirty ? '— Neuložené změny —' : '— Připraveno —')}</div>
      </section>
    </div>
  );
}

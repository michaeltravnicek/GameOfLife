import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import RequireAdmin from '../../components/RequireAdmin/RequireAdmin';
import { createEvent, fetchCategories, fetchBadges } from '../../services/api';
import { invalidateEventLists } from '../../services/queryKeys';
import { extractApiError, reportError } from '../../services/errors';
import { useEventForm, buildEventFormData } from './eventForm';
import EventFormSections from './EventFormSections';
import PageStage from '../../components/PageStage/PageStage';
import PageState from '../../components/PageState/PageState';
import '../../styles/edit-form.css';
import './EventPage.css';

const LOADING = <div className="gol-form-page event-page"><PageState kind="loading" fill text="Načítání…" /></div>;

export default function CreateEventPage() {
  return <RequireAdmin fallback={LOADING}><CreateEventForm /></RequireAdmin>;
}

function CreateEventForm() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const eventForm = useEventForm();
  const {
    form, categories, allCategories, setAllCategories, setBadges,
    dirty, saving, setSaving, saveError, setSaveError, poster,
  } = eventForm;

  useEffect(() => {
    let cancelled = false;
    // Badges are the logo picker's options, so they gate the form the same way
    // categories do — load both before showing it.
    Promise.all([fetchCategories(), fetchBadges()])
      .then(([cats, badgeData]) => {
        if (cancelled) return;
        if (cats?.categories) setAllCategories(cats.categories);
        if (badgeData?.badges) setBadges(badgeData.badges);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        reportError('Nepodařilo se načíst kategorie a odznaky.', err);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [setAllCategories, setBadges]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const formData = buildEventFormData(form, { poster, allCategories, categories });
      const event = await createEvent(formData);
      // Cached lists would keep omitting the new event until their TTL.
      invalidateEventLists();
      navigate(`/events/${event.slug}`);
    } catch (err) {
      setSaveError(extractApiError(err, 'Chyba při vytváření akce.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return LOADING;

  return (
    <div className="gol-form-page event-page has-stage">
      <PageStage image="gal2" position="center 30%" tint="dim" />

      <section className="gol-head">
        <div className="gol-crumb"><Link to="/events">Akce</Link> · Vytvořit</div>
        <div className="gol-eyebrow">Nová akce</div>
        <h1>Vytvořit akci</h1>
      </section>

      <main className="gol-main">
        <EventFormSections state={eventForm} />
      </main>

      <section className="gol-commit-zone">
        <div className="gol-commit-label">— Hotovo? —</div>
        <h2>Vytvořit akci</h2>
        <div className="gol-commit-row">
          <Link className="gol-btn ghost" to="/events">Zrušit</Link>
          <button type="button" className="gol-btn primary lg" onClick={handleSave} disabled={saving}>{saving ? 'Vytvářím…' : 'Vytvořit akci'}</button>
        </div>
        <div className={`gol-commit-note${saveError || dirty ? ' is-pending' : ''}`}>{saveError ? `Chyba: ${saveError}` : (dirty ? 'Neuložené změny' : 'Připraveno')}</div>
      </section>
    </div>
  );
}

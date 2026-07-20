import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Modal from '../../components/Modal/Modal';
import Button from '../../components/Button/Button';
import { useToast } from '../../components/Toast/ToastProvider';
import { fetchEventDetail, updateEvent, deleteEvent, fetchCategories } from '../../services/api';
import { invalidateQuery } from '../../services/queryCache';
import { extractApiError, reportError } from '../../services/errors';
import { useEventForm, eventToForm, buildEventFormData } from './eventForm';
import EventFormSections from './EventFormSections';
import './EventPage.css';

export default function EditEventPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const {
    form, setForm, categories, setCategories, allCategories, setAllCategories,
    dirty, saving, setSaving, saveError, setSaveError,
    markDirty, setField, handleCategories, poster, logo,
  } = useEventForm();

  useEffect(() => {
    Promise.all([
      fetchEventDetail(slug),
      fetchCategories(),
    ])
      .then(([event, cats]) => {
        if (event) {
          setForm(eventToForm(event));
          if (event.image) poster.setPreview(event.image);
          if (event.logo) logo.setPreview(event.logo);
          if (event.category) setCategories([event.category.name]);
        }
        if (cats?.categories) {
          setAllCategories(cats.categories);
        }
        setLoading(false);
      })
      .catch((err) => {
        reportError('Nepodařilo se načíst akci.', err);
        setLoading(false);
      });
    // Only re-run for a different event; the setters/pickers are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const formData = buildEventFormData(form, { poster, logo, allCategories, categories });
      await updateEvent(slug, formData);
      navigate(`/events/${slug}`);
    } catch (err) {
      setSaveError(extractApiError(err, 'Chyba při aktualizaci akce.'));
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await deleteEvent(slug);
      // Deleting cascades to points/RSVPs — drop everything derived from them.
      invalidateQuery((k) => k.startsWith('events:') || k.startsWith('leaderboard:')
        || k.startsWith('gallery') || k === 'hero' || k === 'checkin-events'
        || k.startsWith('profile:') || k.startsWith('player:'));
      toast.success(`Akce „${form.name}“ byla smazána.`, { title: 'Smazáno' });
      navigate('/events');
    } catch (err) {
      setDeleteOpen(false);
      toast.error(extractApiError(err, 'Akci se nepodařilo smazat.'), { title: 'Chyba' });
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return <div className="event-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítání akce…</div></div>;
  }

  return (
    <div className="event-page">
      <div className="ev-stage" aria-hidden="true" />
      <div className="ev-grain" aria-hidden="true" />

      <section className="ev-head">
        <div className="ev-crumb">— <Link to={`/events/${slug}`}>{form.name}</Link> · Upravit —</div>
        <div className="ev-eyebrow">Úprava akce</div>
        <h1>Upravit akci</h1>
      </section>

      <main className="ev-main">
        <EventFormSections
          form={form}
          setForm={setForm}
          setField={setField}
          markDirty={markDirty}
          poster={poster}
          logo={logo}
          allCategories={allCategories}
          categories={categories}
          onCategories={handleCategories}
        />

        {/* 08 · Konec akce */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card ev-danger-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 08 · Konec akce —</div>
              <h2 className="ev-sec-heading">Smazat <span className="pink">akci.</span></h2>
              <p className="ev-sec-sub">Nevratné. S akcí zmizí i všechny udělené body, RSVP a fotky.</p>
            </div>
            <div className="ev-toggle-row">
              <div className="ev-txt"><h4>Smazat akci</h4><p>Hráčům se odečtou body získané na této akci.</p></div>
              <button type="button" className="ev-btn danger" onClick={() => setDeleteOpen(true)}>Smazat akci</button>
            </div>
          </div>
        </section>
      </main>

      <Modal open={deleteOpen} onClose={deleting ? undefined : () => setDeleteOpen(false)} labelledBy="ev-delete-title" width={480}>
        <div className="ev-modal-eyebrow">— Konec akce —</div>
        <h3 id="ev-delete-title" className="ev-modal-title">Smazat akci <span className="pink">natrvalo?</span></h3>
        <p className="ev-modal-text">„{form.name}“ zmizí i se všemi udělenými body, RSVP a fotkami. Tohle vzít zpět nejde.</p>
        <div className="ev-modal-buttons">
          <Button variant="frost" onClick={() => setDeleteOpen(false)} disabled={deleting}>Zpět</Button>
          <Button variant="action" onClick={confirmDelete} busy={deleting}>Smazat natrvalo</Button>
        </div>
      </Modal>

      <section className="ev-commit-zone">
        <div className="ev-commit-label">— Hotovo? —</div>
        <h2>Uložit změny</h2>
        <div className="ev-commit-row">
          <Link className="ev-btn ghost" to={`/events/${slug}`}>Zrušit</Link>
          <button type="button" className="ev-btn primary lg" onClick={handleSave} disabled={saving}>{saving ? 'Ukládám…' : 'Uložit akci'}</button>
        </div>
        <div className="ev-commit-note">{saveError ? `— Chyba: ${saveError} —` : (dirty ? '— Neuložené změny —' : '— Vše uloženo —')}</div>
      </section>

      {/* Slides up as soon as anything changes — mirrors EditProfile's save bar. */}
      <div className={`ev-savebar${dirty ? ' visible' : ''}`}>
        <div className="ev-savebar-inner">
          <div className="ev-status"><span className="ev-pulse" />{saveError || 'Neuložené změny'}</div>
          <div className="ev-savebar-actions">
            <Link className="ev-btn ghost" to={`/events/${slug}`}>Zrušit</Link>
            <button type="button" className="ev-btn primary" onClick={handleSave} disabled={saving}>{saving ? 'Ukládám…' : 'Uložit změny'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

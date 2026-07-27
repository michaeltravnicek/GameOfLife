import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Modal from '../../components/Modal/Modal';
import Button from '../../components/Button/Button';
import { useToast } from '../../components/Toast/ToastProvider';
import { fetchEventDetail, updateEvent, deleteEvent, fetchCategories, fetchBadges } from '../../services/api';
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
  const [badges, setBadges] = useState([]);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const {
    form, setForm, categories, setCategories, allCategories, setAllCategories,
    dirty, saving, setSaving, saveError, setSaveError,
    markDirty, setField, handleCategories, poster,
  } = useEventForm();

  useEffect(() => {
    Promise.all([
      fetchEventDetail(slug),
      fetchCategories(),
      fetchBadges(),
    ])
      .then(([event, cats, badgeData]) => {
        if (event) {
          setForm(eventToForm(event));
          if (event.image) poster.setPreview(event.image);
          // No logo preview to restore: the artwork belongs to the badge, and
          // the badge section renders it from the loaded list.
          if (event.category) setCategories([event.category.name]);
        }
        if (cats?.categories) {
          setAllCategories(cats.categories);
        }
        if (badgeData?.badges) setBadges(badgeData.badges);
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
      const formData = buildEventFormData(form, { poster, allCategories, categories });
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
    return <div className="gol-form-page event-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítání akce…</div></div>;
  }

  return (
    <div className="gol-form-page event-page">
      <div className="ev-stage" aria-hidden="true" />
      <div className="gol-grain" aria-hidden="true" />

      <section className="gol-head">
        <div className="gol-crumb">— <Link to={`/events/${slug}`}>{form.name}</Link> · Upravit —</div>
        <div className="gol-eyebrow">Úprava akce</div>
        <h1>Upravit akci</h1>
      </section>

      <main className="gol-main">
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

        {/* 08 · Konec akce */}
        <section className="gol-section">
          <div className="gol-sec-rule" />
          <div className="gol-card gol-danger-card">
            <div className="gol-card-head">
              <div className="gol-sec-eyebrow">— 08 · Konec akce —</div>
              <h2 className="gol-sec-heading">Smazat <span className="pink">akci.</span></h2>
              <p className="ev-sec-sub">Nevratné. S akcí zmizí i všechny udělené body, RSVP a fotky.</p>
            </div>
            <div className="gol-toggle-row">
              <div className="gol-txt"><h4>Smazat akci</h4><p>Hráčům se odečtou body získané na této akci.</p></div>
              <button type="button" className="gol-btn danger" onClick={() => setDeleteOpen(true)}>Smazat akci</button>
            </div>
          </div>
        </section>
      </main>

      <Modal open={deleteOpen} onClose={deleting ? undefined : () => setDeleteOpen(false)} labelledBy="ev-delete-title" width={480}>
        <div className="gol-modal-eyebrow">— Konec akce —</div>
        <h3 id="ev-delete-title" className="gol-modal-title">Smazat akci <span className="pink">natrvalo?</span></h3>
        <p className="gol-modal-text">„{form.name}“ zmizí i se všemi udělenými body, RSVP a fotkami. Tohle vzít zpět nejde.</p>
        <div className="gol-modal-buttons">
          <Button variant="frost" onClick={() => setDeleteOpen(false)} disabled={deleting}>Zpět</Button>
          <Button variant="action" onClick={confirmDelete} busy={deleting}>Smazat natrvalo</Button>
        </div>
      </Modal>

      <section className="gol-commit-zone">
        <div className="gol-commit-label">— Hotovo? —</div>
        <h2>Uložit změny</h2>
        <div className="gol-commit-row">
          <Link className="gol-btn ghost" to={`/events/${slug}`}>Zrušit</Link>
          <button type="button" className="gol-btn primary lg" onClick={handleSave} disabled={saving}>{saving ? 'Ukládám…' : 'Uložit akci'}</button>
        </div>
        <div className="gol-commit-note">{saveError ? `— Chyba: ${saveError} —` : (dirty ? '— Neuložené změny —' : '— Vše uloženo —')}</div>
      </section>

      {/* Slides up as soon as anything changes — mirrors EditProfile's save bar. */}
      <div className={`gol-savebar${dirty ? ' visible' : ''}`}>
        <div className="gol-savebar-inner">
          <div className="gol-status"><span className="gol-pulse" />{saveError || 'Neuložené změny'}</div>
          <div className="gol-savebar-actions">
            <Link className="gol-btn ghost" to={`/events/${slug}`}>Zrušit</Link>
            <button type="button" className="gol-btn primary" onClick={handleSave} disabled={saving}>{saving ? 'Ukládám…' : 'Uložit změny'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

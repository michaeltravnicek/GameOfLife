import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Switch from '../../components/Switch/Switch';
import ChipSelect from '../../components/ChipSelect/ChipSelect';
import EventLocationMap from '../../components/EventLocationMap/EventLocationMap';
import { createEvent, fetchCategories } from '../../services/api';
import { useImagePreview } from '../../hooks/useImagePreview';
import { useBeforeUnload } from '../../hooks/useBeforeUnload';
import { extractApiError } from '../../services/errors';
import './EventPage.css';

export default function CreateEventPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [allCategories, setAllCategories] = useState([]);
  const [form, setForm] = useState({
    name: '',
    description: '',
    place: '',
    date: '',
    end_date: '',
    points: '',
    capacity: '',
    rules: '',
    survey_url: '',
    visible_to_users: true,
    visible_to_close: false,
    latitude: '',
    longitude: '',
    checkin_radius: '500',
  });
  const [categories, setCategories] = useState([]);

  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const markDirty = () => {
    setDirty(true);
    setSaveError(null);
  };

  const poster = useImagePreview({ onChange: markDirty });
  const logo = useImagePreview({ onChange: markDirty });

  useEffect(() => {
    fetchCategories()
      .then((data) => {
        if (data?.categories) {
          setAllCategories(data.categories);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load categories:', err);
        setLoading(false);
      });
  }, []);

  const setField = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
    markDirty();
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const formData = new FormData();
      formData.append('name', form.name);
      formData.append('description', form.description);
      formData.append('place', form.place);
      if (form.date) formData.append('date', form.date);
      if (form.end_date) formData.append('end_date', form.end_date);
      formData.append('points', form.points || 0);
      if (form.capacity) formData.append('capacity', form.capacity);
      formData.append('rules', form.rules);
      formData.append('survey_url', form.survey_url);
      formData.append('visible_to_users', form.visible_to_users ? '1' : '0');
      formData.append('visible_to_close', form.visible_to_close ? '1' : '0');
      if (form.latitude) formData.append('latitude', form.latitude);
      if (form.longitude) formData.append('longitude', form.longitude);
      formData.append('checkin_radius', form.checkin_radius);
      if (poster.file) formData.append('image', poster.file);
      if (logo.file) formData.append('logo', logo.file);
      const nameToId = new Map(allCategories.map((c) => [c.name, c.id]));
      categories.forEach((name) => {
        const id = nameToId.get(name);
        if (id != null) formData.append('category', id);
      });

      const event = await createEvent(formData);
      navigate(`/events/${event.slug}`);
    } catch (err) {
      setSaveError(extractApiError(err, 'Chyba při vytváření akce.'));
    } finally {
      setSaving(false);
    }
  };

  const handleCategories = (next) => { setCategories(next); markDirty(); };

  useBeforeUnload(dirty);

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
        {/* 01 · Základy */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 01 · Základy —</div>
              <h2 className="ev-sec-heading">Jak se <span className="pink">jmenuje.</span></h2>
              <p className="ev-sec-sub">Základní informace o akci — název, popis a kde se to bude dít.</p>
            </div>
            <div className="ev-grid-2">
              <div className="ev-field">
                <label htmlFor="f-name">Název akce</label>
                <input className="ev-input" id="f-name" value={form.name} onChange={setField('name')} placeholder="Bikepacking" />
              </div>
              <div className="ev-field">
                <label htmlFor="f-place">Místo</label>
                <input className="ev-input" id="f-place" value={form.place} onChange={setField('place')} placeholder="Brno" />
              </div>
              <div className="ev-field ev-full">
                <label htmlFor="f-desc">Popis</label>
                <textarea className="ev-textarea" id="f-desc" placeholder="Podrobný popis akce…" value={form.description} onChange={setField('description')} />
              </div>
            </div>
          </div>
        </section>

        {/* 02 · Čas a body */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 02 · Čas a body —</div>
              <h2 className="ev-sec-heading">Kdy a za <span className="pink">kolik.</span></h2>
              <p className="ev-sec-sub">Nastav datum, čas (lze nechat prázdné) a počet bodů za účast.</p>
            </div>
            <div className="ev-grid-2">
              <div className="ev-field">
                <label htmlFor="f-date">Začátek akce <span className="ev-hint">nepovinné</span></label>
                <input className="ev-input" id="f-date" type="datetime-local" value={form.date} onChange={setField('date')} />
              </div>
              <div className="ev-field">
                <label htmlFor="f-end-date">Konec check-in okna <span className="ev-hint">nepovinné · jinak +4 h</span></label>
                <input className="ev-input" id="f-end-date" type="datetime-local" value={form.end_date} onChange={setField('end_date')} />
              </div>
              <div className="ev-field">
                <label htmlFor="f-points">Body</label>
                <input className="ev-input" id="f-points" type="number" value={form.points} onChange={setField('points')} placeholder="10" />
              </div>
              <div className="ev-field">
                <label htmlFor="f-capacity">Kapacita <span className="ev-hint">nepovinné</span></label>
                <input className="ev-input" id="f-capacity" type="number" value={form.capacity} onChange={setField('capacity')} placeholder="30" />
              </div>
              <div className="ev-field">
                <label htmlFor="f-checkin-radius">Check-in poloměr (m)</label>
                <input className="ev-input" id="f-checkin-radius" type="number" value={form.checkin_radius} onChange={setField('checkin_radius')} />
              </div>
            </div>
          </div>
        </section>

        {/* 03 · Poloha */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 03 · Poloha na mapě —</div>
              <h2 className="ev-sec-heading">Kde se to <span className="pink">děje.</span></h2>
              <p className="ev-sec-sub">Klikni na mapu pro výběr místa. Tažením kolíku ho doladíš.</p>
            </div>
            <EventLocationMap
              interactive
              latitude={form.latitude}
              longitude={form.longitude}
              radius={Number(form.checkin_radius) || 0}
              onChange={({ latitude, longitude }) => {
                setForm((f) => ({ ...f, latitude, longitude }));
                markDirty();
              }}
            />
            {form.latitude !== '' && form.longitude !== '' && (
              <div className="ev-map-meta">
                <span>{Number(form.latitude).toFixed(5)}, {Number(form.longitude).toFixed(5)}</span>
                <button
                  type="button"
                  className="ev-map-clear"
                  onClick={() => { setForm((f) => ({ ...f, latitude: '', longitude: '' })); markDirty(); }}
                >
                  Vymazat polohu
                </button>
              </div>
            )}
          </div>
        </section>

        {/* 04 · Obrázky */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 04 · Vizuál —</div>
              <h2 className="ev-sec-heading">Jak <span className="pink">vypadá.</span></h2>
              <p className="ev-sec-sub">Nahraj plakát a logo akce. PNG nebo JPG, alespoň 400×400 px.</p>
            </div>
            <div className="ev-image-pair">
              <div className="ev-img-section">
                <div className="ev-img-label">Plakát</div>
                <div
                  className={`ev-img-preview${poster.preview ? ' has-img' : ''}`}
                  style={poster.preview ? { backgroundImage: `url(${poster.preview})` } : undefined}
                />
                <div className="ev-img-actions">
                  <label className="ev-btn primary" htmlFor="image-input">Nahrát obrázek
                    <input type="file" id="image-input" accept="image/*" hidden onChange={poster.onSelect} />
                  </label>
                  {poster.preview && <button type="button" className="ev-btn ghost" onClick={poster.clear}>Odebrat</button>}
                </div>
              </div>
              <div className="ev-img-section">
                <div className="ev-img-label">Logo</div>
                <div
                  className={`ev-img-preview sm${logo.preview ? ' has-img' : ''}`}
                  style={logo.preview ? { backgroundImage: `url(${logo.preview})` } : undefined}
                />
                <div className="ev-img-actions">
                  <label className="ev-btn primary" htmlFor="logo-input">Nahrát logo
                    <input type="file" id="logo-input" accept="image/*" hidden onChange={logo.onSelect} />
                  </label>
                  {logo.preview && <button type="button" className="ev-btn ghost" onClick={logo.clear}>Odebrat</button>}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 05 · Kategorie */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 05 · Kategorie —</div>
              <h2 className="ev-sec-heading">V jaké <span className="pink">kategorii.</span></h2>
              <p className="ev-sec-sub">Vyber jednu nebo více kategorií, do kterých akce patří.</p>
            </div>
            <ChipSelect options={allCategories.map((c) => c.name)} selected={categories} onChange={handleCategories} max={1} />
          </div>
        </section>

        {/* 06 · Pravidla a formulář */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 06 · Obsah —</div>
              <h2 className="ev-sec-heading">Jaká <span className="pink">pravidla.</span></h2>
              <p className="ev-sec-sub">Postup, řád, instrukce… a odkaz na dotazník (Google Forms).</p>
            </div>
            <div className="ev-field ev-full">
              <label htmlFor="f-rules">Pravidla</label>
              <textarea className="ev-textarea" id="f-rules" placeholder="Každé pravidlo na nový řádek…" value={form.rules} onChange={setField('rules')} />
            </div>
            <div className="ev-field ev-full">
              <label htmlFor="f-survey">URL dotazníku (Google Forms)</label>
              <input className="ev-input" id="f-survey" type="url" placeholder="https://forms.google.com/…" value={form.survey_url} onChange={setField('survey_url')} />
            </div>
          </div>
        </section>


        {/* 07 · Viditelnost */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-card">
            <div className="ev-card-head">
              <div className="ev-sec-eyebrow">— 07 · Viditelnost —</div>
              <h2 className="ev-sec-heading">Kdo <span className="pink">uvidí.</span></h2>
              <p className="ev-sec-sub">Postav si, zda je akce viditelná pro běžné uživatele.</p>
            </div>
            <div className="ev-toggle-row">
              <div className="ev-txt"><h4>Viditelná pro uživatele</h4><p>Pokud vypnuto, akce se zobrazí jen v adminu.</p></div>
              <Switch checked={form.visible_to_users} onChange={(val) => { setForm((f) => ({ ...f, visible_to_users: val })); markDirty(); }} ariaLabel="Viditelná pro uživatele" />
            </div>
            <div className="ev-toggle-row">
              <div className="ev-txt"><h4>Náhled pro Close</h4><p>Close uvidí akci dříve než ostatní uživatelé (i když je vypnuto výše).</p></div>
              <Switch checked={form.visible_to_close} onChange={(val) => { setForm((f) => ({ ...f, visible_to_close: val })); markDirty(); }} ariaLabel="Náhled pro Close" />
            </div>
          </div>
        </section>
      </main>

      <section className="ev-commit-zone">
        <div className="ev-commit-label">— Hotovo? —</div>
        <h2>Vytvořit akci</h2>
        <div className="ev-commit-row">
          <Link className="ev-btn ghost" to="/events">Zrušit</Link>
          <button type="button" className="ev-btn primary lg" onClick={handleSave} disabled={saving}>{saving ? 'Vytvářím…' : 'Vytvořit akci'}</button>
        </div>
        <div className="ev-commit-note">{saveError ? `— Chyba: ${saveError} —` : (dirty ? '— Neuložené změny —' : '— Připraveno —')}</div>
      </section>
    </div>
  );
}

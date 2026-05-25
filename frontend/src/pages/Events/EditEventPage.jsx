import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Switch from '../../components/Switch/Switch';
import ChipSelect from '../../components/ChipSelect/ChipSelect';
import { fetchEventDetail, updateEvent, fetchCategories } from '../../services/api';
import './EventPage.css';

export default function EditEventPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [allCategories, setAllCategories] = useState([]);
  const [form, setForm] = useState({
    name: '',
    description: '',
    place: '',
    date: '',
    points: '',
    capacity: '',
    rules: '',
    survey_url: '',
    visible_to_users: true,
    latitude: '',
    longitude: '',
    checkin_radius: '500',
  });
  const [image, setImage] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [logo, setLogo] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [categories, setCategories] = useState([]);

  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetchEventDetail(slug),
      fetchCategories(),
    ])
      .then(([event, cats]) => {
        if (event) {
          setForm({
            name: event.name || '',
            description: event.description || '',
            place: event.place || '',
            date: event.date ? event.date.slice(0, 16) : '',
            points: event.points || '',
            capacity: event.capacity || '',
            rules: event.rules || '',
            survey_url: event.survey_url || '',
            visible_to_users: event.visible_to_users ?? true,
            latitude: event.latitude || '',
            longitude: event.longitude || '',
            checkin_radius: event.checkin_radius || '500',
          });
          if (event.image) setImage(event.image);
          if (event.logo) setLogo(event.logo);
          if (event.category) setCategories([event.category.name]);
        }
        if (cats?.categories) {
          setAllCategories(cats.categories);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load:', err);
        setLoading(false);
      });
  }, [slug]);

  const markDirty = () => {
    setDirty(true);
    setSaveError(null);
  };

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
      formData.append('points', form.points || 0);
      if (form.capacity) formData.append('capacity', form.capacity);
      formData.append('rules', form.rules);
      formData.append('survey_url', form.survey_url);
      formData.append('visible_to_users', form.visible_to_users ? '1' : '0');
      if (form.latitude) formData.append('latitude', form.latitude);
      if (form.longitude) formData.append('longitude', form.longitude);
      formData.append('checkin_radius', form.checkin_radius);
      if (imageFile) formData.append('image', imageFile);
      if (logoFile) formData.append('logo', logoFile);
      const nameToId = new Map(allCategories.map((c) => [c.name, c.id]));
      categories.forEach((name) => {
        const id = nameToId.get(name);
        if (id != null) formData.append('category', id);
      });

      await updateEvent(slug, formData);
      navigate(`/akce/${slug}`);
    } catch (err) {
      setSaveError(err.response?.data?.error || 'Chyba při aktualizaci akce.');
    } finally {
      setSaving(false);
    }
  };

  const handleImage = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setImage(reader.result); };
    reader.readAsDataURL(file);
    setImageFile(file);
    markDirty();
  };

  const removeImage = () => { setImage(null); setImageFile(null); markDirty(); };

  const handleLogo = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setLogo(reader.result); };
    reader.readAsDataURL(file);
    setLogoFile(file);
    markDirty();
  };

  const removeLogo = () => { setLogo(null); setLogoFile(null); markDirty(); };

  const handleCategories = (next) => { setCategories(next); markDirty(); };

  useEffect(() => {
    if (!dirty) return undefined;
    const onBeforeUnload = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  if (loading) {
    return <div className="event-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítání akce…</div></div>;
  }

  return (
    <div className="event-page">
      <div className="ev-stage" aria-hidden="true" />
      <div className="ev-grain" aria-hidden="true" />

      <section className="ev-head">
        <div className="ev-crumb">— <Link to={`/akce/${slug}`}>{form.name}</Link> · Upravit —</div>
        <div className="ev-eyebrow">Úprava akce</div>
        <h1>Upravit akci</h1>
        <p className="ev-lede">Změň detaily akce — název, popis, čas, body, nebo vizuál.</p>
        <div className="ev-divider" />
      </section>

      <main className="ev-main">
        {/* 01 · Základy */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-sec-eyebrow">— 01 · Základy —</div>
          <h2 className="ev-sec-heading">Jak se <span className="pink">jmenuje.</span></h2>
          <p className="ev-sec-sub">Základní informace o akci — název, popis a kde se to bude dít.</p>
          <div className="ev-card">
            <div className="ev-grid-2">
              <div className="ev-field">
                <label htmlFor="f-name">Název akce</label>
                <input className="ev-input" id="f-name" value={form.name} onChange={setField('name')} />
              </div>
              <div className="ev-field">
                <label htmlFor="f-place">Místo</label>
                <input className="ev-input" id="f-place" value={form.place} onChange={setField('place')} />
              </div>
              <div className="ev-field ev-full">
                <label htmlFor="f-desc">Popis</label>
                <textarea className="ev-textarea" id="f-desc" value={form.description} onChange={setField('description')} />
              </div>
            </div>
          </div>
        </section>

        {/* 02 · Čas a body */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-sec-eyebrow">— 02 · Čas a body —</div>
          <h2 className="ev-sec-heading">Kdy a za <span className="pink">kolik.</span></h2>
          <p className="ev-sec-sub">Nastav datum, čas (lze nechat prázdné) a počet bodů za účast.</p>
          <div className="ev-card">
            <div className="ev-grid-2">
              <div className="ev-field">
                <label htmlFor="f-date">Datum a čas <span className="ev-hint">nepovinné</span></label>
                <input className="ev-input" id="f-date" type="datetime-local" value={form.date} onChange={setField('date')} />
              </div>
              <div className="ev-field">
                <label htmlFor="f-points">Body</label>
                <input className="ev-input" id="f-points" type="number" value={form.points} onChange={setField('points')} />
              </div>
              <div className="ev-field">
                <label htmlFor="f-capacity">Kapacita <span className="ev-hint">nepovinné</span></label>
                <input className="ev-input" id="f-capacity" type="number" value={form.capacity} onChange={setField('capacity')} />
              </div>
              <div className="ev-field">
                <label htmlFor="f-checkin-radius">Check-in poloměr (m)</label>
                <input className="ev-input" id="f-checkin-radius" type="number" value={form.checkin_radius} onChange={setField('checkin_radius')} />
              </div>
            </div>
          </div>
        </section>

        {/* 03 · Obrázky */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-sec-eyebrow">— 03 · Vizuál —</div>
          <h2 className="ev-sec-heading">Jak <span className="pink">vypadá.</span></h2>
          <p className="ev-sec-sub">Nahraj plakát a logo akce. PNG nebo JPG, alespoň 400×400 px.</p>
          <div className="ev-card">
            <div className="ev-image-pair">
              <div className="ev-img-section">
                <div className="ev-img-label">Plakát</div>
                <div
                  className={`ev-img-preview${image ? ' has-img' : ''}`}
                  style={image ? { backgroundImage: `url(${image})` } : undefined}
                />
                <div className="ev-img-actions">
                  <label className="ev-btn primary" htmlFor="image-input">Nahrát obrázek
                    <input type="file" id="image-input" accept="image/*" hidden onChange={handleImage} />
                  </label>
                  {image && <button type="button" className="ev-btn ghost" onClick={removeImage}>Odebrat</button>}
                </div>
              </div>
              <div className="ev-img-section">
                <div className="ev-img-label">Logo</div>
                <div
                  className={`ev-img-preview sm${logo ? ' has-img' : ''}`}
                  style={logo ? { backgroundImage: `url(${logo})` } : undefined}
                />
                <div className="ev-img-actions">
                  <label className="ev-btn primary" htmlFor="logo-input">Nahrát logo
                    <input type="file" id="logo-input" accept="image/*" hidden onChange={handleLogo} />
                  </label>
                  {logo && <button type="button" className="ev-btn ghost" onClick={removeLogo}>Odebrat</button>}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 04 · Kategorie */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-sec-eyebrow">— 04 · Kategorie —</div>
          <h2 className="ev-sec-heading">V jaké <span className="pink">kategorii.</span></h2>
          <p className="ev-sec-sub">Vyber jednu nebo více kategorií, do kterých akce patří.</p>
          <div className="ev-card">
            <ChipSelect options={allCategories.map((c) => c.name)} selected={categories} onChange={handleCategories} max={1} />
          </div>
        </section>

        {/* 05 · Pravidla a formulář */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-sec-eyebrow">— 05 · Obsah —</div>
          <h2 className="ev-sec-heading">Jaká <span className="pink">pravidla.</span></h2>
          <p className="ev-sec-sub">Postup, řád, instrukce… a odkaz na dotazník (Google Forms).</p>
          <div className="ev-card">
            <div className="ev-field ev-full">
              <label htmlFor="f-rules">Pravidla</label>
              <textarea className="ev-textarea" id="f-rules" value={form.rules} onChange={setField('rules')} />
            </div>
            <div className="ev-field ev-full">
              <label htmlFor="f-survey">URL dotazníku (Google Forms)</label>
              <input className="ev-input" id="f-survey" type="url" value={form.survey_url} onChange={setField('survey_url')} />
            </div>
          </div>
        </section>

        {/* 06 · Poloha */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-sec-eyebrow">— 06 · Poloha na mapě —</div>
          <h2 className="ev-sec-heading">Kde se to <span className="pink">děje.</span></h2>
          <p className="ev-sec-sub">Geografické souřadnice pro mapu a check-in. Oba nebo nic.</p>
          <div className="ev-card">
            <div className="ev-grid-2">
              <div className="ev-field">
                <label htmlFor="f-lat">Zeměpisná šířka (lat)</label>
                <input className="ev-input" id="f-lat" type="number" step="0.0001" value={form.latitude} onChange={setField('latitude')} />
              </div>
              <div className="ev-field">
                <label htmlFor="f-long">Zeměpisná délka (long)</label>
                <input className="ev-input" id="f-long" type="number" step="0.0001" value={form.longitude} onChange={setField('longitude')} />
              </div>
            </div>
          </div>
        </section>

        {/* 07 · Viditelnost */}
        <section className="ev-section">
          <div className="ev-sec-rule" />
          <div className="ev-sec-eyebrow">— 07 · Viditelnost —</div>
          <h2 className="ev-sec-heading">Kdo <span className="pink">uvidí.</span></h2>
          <p className="ev-sec-sub">Postav si, zda je akce viditelná pro běžné uživatele.</p>
          <div className="ev-card">
            <div className="ev-toggle-row">
              <div className="ev-txt"><h4>Viditelná pro uživatele</h4><p>Pokud vypnuto, akce se zobrazí jen v adminu.</p></div>
              <Switch checked={form.visible_to_users} onChange={setField('visible_to_users')} ariaLabel="Viditelná pro uživatele" />
            </div>
          </div>
        </section>
      </main>

      <section className="ev-commit-zone">
        <div className="ev-commit-label">— Hotovo? —</div>
        <h2>Uložit změny</h2>
        <div className="ev-commit-row">
          <Link className="ev-btn ghost" to={`/akce/${slug}`}>Zrušit</Link>
          <button type="button" className="ev-btn primary lg" onClick={handleSave} disabled={saving}>{saving ? 'Ukládám…' : 'Uložit akci'}</button>
        </div>
        <div className="ev-commit-note">{saveError ? `— Chyba: ${saveError} —` : (dirty ? '— Neuložené změny —' : '— Vše uloženo —')}</div>
      </section>
    </div>
  );
}

import Switch from '../../components/Switch/Switch';
import ChipSelect from '../../components/ChipSelect/ChipSelect';
import EventLocationMap from '../../components/EventLocationMap/EventLocationMap';

/**
 * The shared body of the create/edit event forms — sections 01–07 (Základy,
 * Čas a body, Poloha, Vizuál, Kategorie, Obsah, Viditelnost). Both pages render
 * this identically; only the surrounding chrome (page head, commit bar, and the
 * edit page's delete section) differs, so that stays in the pages.
 *
 * Input placeholders are kept — harmless on the edit form (fields are pre-filled)
 * and a helpful hint if a field is cleared.
 */
export default function EventFormSections({
  form,
  setForm,
  setField,
  markDirty,
  poster,
  logo,
  allCategories,
  categories,
  onCategories,
}) {
  return (
    <>
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
          <div className="ev-toggle-row">
            <div className="ev-txt"><h4>Čas upřesníme</h4><p>Datum zůstane, ale místo přesného času se u akce zobrazí „Upřesníme“.</p></div>
            <Switch checked={form.time_tbd} onChange={(val) => { setForm((f) => ({ ...f, time_tbd: val })); markDirty(); }} ariaLabel="Čas upřesníme" />
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
              {/* The preview renders the logo the same way the site does — an
                  <img> scaled by logo_scale — so the slider shows the real result. */}
              <div className={`ev-img-preview sm${logo.preview ? ' has-img' : ''}`}>
                {logo.preview && (
                  <img
                    className="ev-logo-preview-img"
                    src={logo.preview}
                    alt="Náhled loga"
                    style={{ transform: `scale(${form.logo_scale})` }}
                  />
                )}
              </div>
              <div className="ev-img-actions">
                <label className="ev-btn primary" htmlFor="logo-input">Nahrát logo
                  <input type="file" id="logo-input" accept="image/*" hidden onChange={logo.onSelect} />
                </label>
                {logo.preview && <button type="button" className="ev-btn ghost" onClick={logo.clear}>Odebrat</button>}
              </div>
              {logo.preview && (
                <div className="ev-logo-scale">
                  <div className="ev-logo-scale-head">
                    <label htmlFor="f-logo-scale">Velikost loga</label>
                    <span className="ev-logo-scale-val">{Number(form.logo_scale).toFixed(2)}×</span>
                  </div>
                  <input
                    id="f-logo-scale"
                    type="range"
                    min="0.5"
                    max="2"
                    step="0.05"
                    value={form.logo_scale}
                    onChange={(e) => { setForm((f) => ({ ...f, logo_scale: Number(e.target.value) })); markDirty(); }}
                    aria-label="Velikost loga"
                  />
                </div>
              )}
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
            <p className="ev-sec-sub">Vyber kategorii, do které akce patří.</p>
          </div>
          <ChipSelect options={allCategories.map((c) => c.name)} selected={categories} onChange={onCategories} max={1} />
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
          <div className="ev-field ev-full">
            <label htmlFor="f-whatsapp">Odkaz na WhatsApp skupinu <span className="ev-hint">nepovinné · nabídne se po přihlášení</span></label>
            <input className="ev-input" id="f-whatsapp" type="url" placeholder="https://chat.whatsapp.com/…" value={form.whatsapp_url} onChange={setField('whatsapp_url')} />
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
    </>
  );
}

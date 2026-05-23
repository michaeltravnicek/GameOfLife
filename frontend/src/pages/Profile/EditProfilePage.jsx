import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Switch from '../../components/Switch/Switch';
import ChipSelect from '../../components/ChipSelect/ChipSelect';
import './EditProfilePage.css';

const CATEGORIES = ['Běh', 'Tanec', 'Karaoke', 'Bruslení', 'Akce', 'Festival', 'Plavání', 'Cyklistika', 'Lezení', 'Deskovky'];
const BIO_MAX = 220;

const SOCIALS = [
  { key: 'ig', ico: 'IG', pre: 'instagram.com/', placeholder: 'uživatel' },
  { key: 'st', ico: 'ST', pre: 'strava.com/athletes/', placeholder: 'uživatel' },
  { key: 'sp', ico: 'SP', pre: 'spotify.com/user/', placeholder: 'uživatel' },
  { key: 'tt', ico: 'TT', pre: 'tiktok.com/@', placeholder: 'uživatel' },
];

export default function EditProfilePage() {
  const [form, setForm] = useState({
    name: 'Lukáš Müller',
    handle: 'lukasmuller',
    city: 'Brno, CZ',
    since: '2024-02',
    email: 'lukas@lukasmuller.cz',
    phone: '+420 731 005 976',
    bio: 'Karaoke v sobotu, deskovky ve středu, nahá míle kdykoliv. Každá akce je výmluva potkat lidi, co mají života plné zuby — a chtějí ho prožít naplno.',
  });
  const [avatar, setAvatar] = useState(null);
  const [categories, setCategories] = useState(['Běh', 'Tanec', 'Karaoke']);
  const [socials, setSocials] = useState({ ig: 'lukasmuller', st: 'lukasmuller', sp: 'lukasmuller', tt: '' });
  const [privacy, setPrivacy] = useState({ p_pts: false, p_events: false, p_members: true });

  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [barVisible, setBarVisible] = useState(false);
  const [btnSaved, setBtnSaved] = useState(false);

  const markDirty = () => {
    setDirty(true);
    setSaved(false);
    setBarVisible(true);
  };

  const setField = (key) => (e) => { setForm((f) => ({ ...f, [key]: e.target.value })); markDirty(); };

  const handleSave = () => {
    setDirty(false);
    setSaved(true);
    setBarVisible(true);
    setBtnSaved(true);
  };

  const handleAvatar = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setAvatar(reader.result); markDirty(); };
    reader.readAsDataURL(file);
  };

  const removeAvatar = () => { setAvatar(null); markDirty(); };

  const setSocial = (key) => (e) => { setSocials((s) => ({ ...s, [key]: e.target.value })); markDirty(); };
  const togglePrivacy = (key) => (next) => { setPrivacy((p) => ({ ...p, [key]: next })); markDirty(); };

  const handleCategories = (next) => { setCategories(next); markDirty(); };

  const handlePause = () => {
    if (window.confirm('Opravdu pozastavit účet? Můžeš se kdykoliv vrátit.')) {
      window.alert('Účet pozastaven. Vrať se brzy.');
    }
  };
  const handleDelete = () => {
    if (window.confirm('Smazat účet NATRVALO? Tato akce je nevratná.')) {
      window.alert('… kdyby to bylo opravdu napojený, teď by ses smazal.');
    }
  };

  useEffect(() => {
    if (!dirty) return undefined;
    const onBeforeUnload = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  useEffect(() => {
    if (!saved) return undefined;
    const t = setTimeout(() => setBarVisible(false), 1600);
    return () => clearTimeout(t);
  }, [saved]);

  useEffect(() => {
    if (!btnSaved) return undefined;
    const t = setTimeout(() => setBtnSaved(false), 1400);
    return () => clearTimeout(t);
  }, [btnSaved]);

  const initials = form.name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || 'GO';

  return (
    <div className="editprofile-page">
      <div className="ep-stage" aria-hidden="true" />
      <div className="ep-grain" aria-hidden="true" />

      <section className="ep-head">
        <div className="ep-crumb">— <Link to="/profil">Profil</Link> · Upravit —</div>
        <div className="ep-eyebrow">Tvůj kus stránky</div>
        <h1>Upravit profil</h1>
        <p className="ep-lede">Tady si nastav, jak tě uvidí ostatní hráči — od jména po playlist, kterým je rozsekáš na karaoke.</p>
        <div className="ep-divider" />
      </section>

      <main className="ep-main">
        {/* 01 · Základy */}
        <section className="ep-section">
          <div className="ep-sec-rule" />
          <div className="ep-sec-eyebrow">— 01 · Základy —</div>
          <h2 className="ep-sec-heading">Kdo <span className="pink">jsi.</span></h2>
          <p className="ep-sec-sub">Tyhle údaje uvidí každý, kdo otevře tvůj profil. Telefon &amp; e-mail jsou jen pro organizátory.</p>
          <div className="ep-card">
            <div className="ep-grid-2">
              <div className="ep-field">
                <label htmlFor="f-name">Jméno &amp; příjmení</label>
                <input className="ep-input" id="f-name" value={form.name} onChange={setField('name')} />
              </div>
              <div className="ep-field">
                <label htmlFor="f-handle">Přezdívka <span className="ep-hint">objeví se jako @handle</span></label>
                <div className="ep-input-prefix"><span className="ep-pre">@</span><input className="ep-input" id="f-handle" value={form.handle} onChange={setField('handle')} /></div>
              </div>
              <div className="ep-field">
                <label htmlFor="f-city">Město</label>
                <input className="ep-input" id="f-city" value={form.city} onChange={setField('city')} placeholder="Brno, CZ" />
              </div>
              <div className="ep-field">
                <label htmlFor="f-since">Hraje od</label>
                <input className="ep-input" id="f-since" type="month" value={form.since} onChange={setField('since')} />
              </div>
              <div className="ep-field">
                <label htmlFor="f-email">E-mail <span className="ep-hint">jen pro organizátory</span></label>
                <input className="ep-input" id="f-email" type="email" value={form.email} onChange={setField('email')} />
              </div>
              <div className="ep-field">
                <label htmlFor="f-phone">Telefon <span className="ep-hint">jen pro organizátory</span></label>
                <input className="ep-input" id="f-phone" type="tel" value={form.phone} onChange={setField('phone')} />
              </div>
            </div>
          </div>
        </section>

        {/* 02 · Avatar */}
        <section className="ep-section">
          <div className="ep-sec-rule" />
          <div className="ep-sec-eyebrow">— 02 · Avatar &amp; identita —</div>
          <h2 className="ep-sec-heading">Jak <span className="pink">vypadáš.</span></h2>
          <p className="ep-sec-sub">Tvoje fotka se objeví u tvého jména v leaderboardu, v galerii akcí a vedle každé tvojí RSVP.</p>
          <div className="ep-card ep-avatar-card">
            <div
              className={`ep-avatar-big${avatar ? ' has-img' : ''}`}
              style={avatar ? { backgroundImage: `url(${avatar})` } : undefined}
            >
              {!avatar && initials}
            </div>
            <div className="ep-avatar-meta">
              <div className="ep-l">— Profilová fotka —</div>
              <div className="ep-h">{form.name}</div>
              <div className="ep-s">JPG nebo PNG, alespoň 400×400 px. Co tam dáš — z toho ti budou ostatní vařit kávu.</div>
              <div className="ep-avatar-actions">
                <label className="ep-btn primary" htmlFor="avatar-input">Nahrát fotku
                  <input type="file" id="avatar-input" accept="image/*" hidden onChange={handleAvatar} />
                </label>
                <button type="button" className="ep-btn ghost" onClick={removeAvatar}>Odebrat</button>
              </div>
            </div>
          </div>
        </section>

        {/* 03 · Bio */}
        <section className="ep-section">
          <div className="ep-sec-rule" />
          <div className="ep-sec-eyebrow">— 03 · O mně —</div>
          <h2 className="ep-sec-heading">Co o sobě <span className="pink">povíš.</span></h2>
          <p className="ep-sec-sub">Krátký vzkaz, který se objeví v záhlaví tvého profilu. Drž to v jednom dechu — nejvíc 220 znaků.</p>
          <div className="ep-card">
            <div className="ep-field ep-full">
              <label htmlFor="f-bio">Bio</label>
              <textarea
                className="ep-textarea"
                id="f-bio"
                maxLength={BIO_MAX}
                placeholder="Karaoke v sobotu, deskovky ve středu…"
                value={form.bio}
                onChange={setField('bio')}
              />
              <div className="ep-counter">{form.bio.length} / {BIO_MAX} znaků</div>
            </div>
          </div>
        </section>

        {/* 04 · Kategorie */}
        <section className="ep-section">
          <div className="ep-sec-rule" />
          <div className="ep-sec-eyebrow">— 04 · Oblíbené kategorie —</div>
          <h2 className="ep-sec-heading">V čem <span className="pink">jedeš.</span></h2>
          <p className="ep-sec-sub">Vyber 1–4 kategorie, ve kterých se nejvíc realizuješ. Pomůže nám doporučit ti akce na míru.</p>
          <div className="ep-card">
            <ChipSelect options={CATEGORIES} selected={categories} onChange={handleCategories} max={4} />
          </div>
        </section>

        {/* 05 · Sociální sítě */}
        <section className="ep-section">
          <div className="ep-sec-rule" />
          <div className="ep-sec-eyebrow">— 05 · Sociální sítě —</div>
          <h2 className="ep-sec-heading">Kde tě <span className="pink">najdou.</span></h2>
          <p className="ep-sec-sub">Tyhle odkazy se objeví v sekci „O mně“ na tvém profilu. Nech prázdné, co nechceš sdílet.</p>
          <div className="ep-card">
            <div className="ep-social-rows">
              {SOCIALS.map((s) => (
                <div key={s.key} className={`ep-social-row${socials[s.key].trim() ? ' filled' : ''}`}>
                  <span className="ep-ico">{s.ico}</span>
                  <div className="ep-combo">
                    <span className="ep-pre">{s.pre}</span>
                    <input className="ep-input" value={socials[s.key]} onChange={setSocial(s.key)} placeholder={s.placeholder} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 06 · Soukromí */}
        <section className="ep-section">
          <div className="ep-sec-rule" />
          <div className="ep-sec-eyebrow">— 06 · Soukromí —</div>
          <h2 className="ep-sec-heading">Kdo tě <span className="pink">uvidí.</span></h2>
          <p className="ep-sec-sub">Profil je veřejný, ale tyhle detaily můžeš zamknout.</p>
          <div className="ep-card">
            <div className="ep-toggle-row">
              <div className="ep-txt"><h4>Skrýt celkové body</h4><p>Tvoje pozice v leaderboardu zůstane, body neuvidí nikdo kromě tebe.</p></div>
              <Switch checked={privacy.p_pts} onChange={togglePrivacy('p_pts')} ariaLabel="Skrýt celkové body" />
            </div>
            <div className="ep-toggle-row">
              <div className="ep-txt"><h4>Skrýt seznam absolvovaných akcí</h4><p>Tvůj profil ukáže jen highlighty.</p></div>
              <Switch checked={privacy.p_events} onChange={togglePrivacy('p_events')} ariaLabel="Skrýt seznam akcí" />
            </div>
            <div className="ep-toggle-row">
              <div className="ep-txt"><h4>Profil pouze pro členy</h4><p>Nepřihlášení návštěvníci uvidí jen jméno a fotku.</p></div>
              <Switch checked={privacy.p_members} onChange={togglePrivacy('p_members')} ariaLabel="Profil pouze pro členy" />
            </div>
          </div>
        </section>

        {/* 07 · Danger */}
        <section className="ep-section">
          <div className="ep-sec-rule" />
          <div className="ep-sec-eyebrow danger">— 07 · Konec hry —</div>
          <h2 className="ep-sec-heading">Něco <span className="pink">extrémního.</span></h2>
          <p className="ep-sec-sub">Tyhle akce jsou nevratné. Body, akce, fotky — všechno zmizí. Mysli si dvakrát.</p>
          <div className="ep-card ep-danger-card">
            <div className="ep-toggle-row">
              <div className="ep-txt"><h4>Pozastavit účet</h4><p>Tvůj profil zmizí z leaderboardu, ale data si necháme. Kdykoliv se můžeš vrátit.</p></div>
              <button type="button" className="ep-btn ghost" onClick={handlePause}>Pozastavit</button>
            </div>
            <div className="ep-toggle-row">
              <div className="ep-txt"><h4>Smazat účet</h4><p>Trvalé. Všechny tvoje akce, body i fotky budou ztraceny v čase, jako slzy v dešti.</p></div>
              <button type="button" className="ep-btn danger" onClick={handleDelete}>Smazat účet</button>
            </div>
          </div>
        </section>
      </main>

      <section className="ep-commit-zone">
        <div className="ep-commit-label">— Hotovo? —</div>
        <h2>Uložit změny</h2>
        <div className="ep-commit-row">
          <Link className="ep-btn ghost" to="/profil">Zrušit</Link>
          <button type="button" className="ep-btn primary lg" onClick={handleSave}>{btnSaved ? '✓ Uloženo' : 'Uložit profil'}</button>
        </div>
        <div className="ep-commit-note">{dirty ? '— Neuložené změny —' : '— Vše uloženo —'}</div>
      </section>

      <div className={`ep-savebar${barVisible ? ' visible' : ''}`}>
        <div className="ep-savebar-inner">
          <div className={`ep-status${saved ? ' saved' : ''}`}><span className="ep-pulse" />{saved ? 'Vše uloženo' : 'Neuložené změny'}</div>
          <div className="ep-savebar-actions">
            <Link className="ep-btn ghost" to="/profil">Zrušit</Link>
            <button type="button" className="ep-btn primary" onClick={handleSave}>{btnSaved ? '✓ Uloženo' : 'Uložit změny'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

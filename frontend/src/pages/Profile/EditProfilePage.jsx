import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Switch from '../../components/Switch/Switch';
import ChipSelect from '../../components/ChipSelect/ChipSelect';
import Modal from '../../components/Modal/Modal';
import Button from '../../components/Button/Button';
import { useToast } from '../../components/Toast/ToastProvider';
import {
  fetchMe, fetchProfile, updateProfile, fetchCategories, fetchProfileQuestions,
  apiDeleteAccount,
} from '../../services/api';
import { useBeforeUnload } from '../../hooks/useBeforeUnload';
import { reportError, extractApiError } from '../../services/errors';
import { initials } from '../../utils/name';
import './EditProfilePage.css';

const BIO_MAX = 220;
// Mirrors ANSWER_MAX_LENGTH in accounts/services.py. The server truncates
// anyway; this is so the counter tells the truth before you hit save.
const ANSWER_MAX = 500;

const SOCIALS = [
  { key: 'instagram', ico: 'IG', pre: 'instagram.com/', placeholder: 'uživatel' },
  { key: 'strava', ico: 'ST', pre: 'strava.com/athletes/', placeholder: 'uživatel' },
  { key: 'spotify', ico: 'SP', pre: 'spotify.com/user/', placeholder: 'uživatel' },
  { key: 'tiktok', ico: 'TT', pre: 'tiktok.com/@', placeholder: 'uživatel' },
];

export default function EditProfilePage() {
  const toast = useToast();
  const navigate = useNavigate();
  const { refresh: refreshAuth } = useAuth();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [allCategories, setAllCategories] = useState([]);
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
    city: '',
    bio: '',
  });
  const [avatar, setAvatar] = useState(null);
  const [removePhoto, setRemovePhoto] = useState(false);
  const [avatarFile, setAvatarFile] = useState(null);
  const [categories, setCategories] = useState([]);
  // Questions come from admin; answers are keyed by question id. Both default
  // to empty, so a site with no questions authored yet renders no section.
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [socials, setSocials] = useState({ instagram: '', strava: '', spotify: '', tiktok: '' });
  const [privacy, setPrivacy] = useState({
    hide_pts: false, hide_events: false, members_only: false,
  });

  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [barVisible, setBarVisible] = useState(false);
  const [btnSaved, setBtnSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      fetchMe().then((data) => {
        const username = data.user?.username;
        return username ? fetchProfile(username) : null;
      }),
      fetchCategories(),
      fetchProfileQuestions(),
    ])
      .then(([profile, cats, qs]) => {
        if (profile) {
          setForm({
            first_name: profile.first_name || '',
            last_name: profile.last_name || '',
            username: profile.username,
            email: profile.email || '',
            city: profile.city || '',
            bio: profile.bio || '',
          });
          setCategories((profile.favourite_categories || []).map((c) => c.name));
          setSocials({
            instagram: profile.instagram || '',
            strava: profile.strava || '',
            spotify: profile.spotify || '',
            tiktok: profile.tiktok || '',
          });
          setPrivacy({
            hide_pts: profile.privacy?.hide_pts || false,
            hide_events: profile.privacy?.hide_events || false,
            members_only: profile.privacy?.members_only || false,
          });
          if (profile.photo) {
            setAvatar(profile.photo);
          }
          // The payload only carries answered questions, so anything missing
          // here is genuinely unanswered and starts blank.
          setAnswers(Object.fromEntries(
            (profile.answers || []).map((a) => [a.question_id, a.answer]),
          ));
        }
        if (cats?.categories) {
          setAllCategories(cats.categories);
        }
        if (qs?.questions) {
          setQuestions(qs.questions);
        }
        setLoading(false);
      })
      .catch((err) => {
        reportError('Nepodařilo se načíst profil.', err);
        setLoading(false);
      });
  }, []);

  const markDirty = () => {
    setDirty(true);
    setSaved(false);
    setBarVisible(true);
    setSaveError(null);
  };

  const setField = (key) => (e) => { setForm((f) => ({ ...f, [key]: e.target.value })); markDirty(); };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const formData = new FormData();
      formData.append('first_name', form.first_name);
      formData.append('last_name', form.last_name);
      formData.append('username', form.username);
      formData.append('email', form.email);
      formData.append('city', form.city);
      formData.append('bio', form.bio);
      if (avatarFile) formData.append('photo', avatarFile);
      if (removePhoto) formData.append('remove_photo', '1');
      // ChipSelect works in category names; map them back to ids for the API.
      const nameToId = new Map(allCategories.map((c) => [c.name, c.id]));
      categories.forEach((name) => {
        const id = nameToId.get(name);
        if (id != null) formData.append('favourite_categories', id);
      });
      formData.append('hide_pts', privacy.hide_pts ? '1' : '0');
      formData.append('hide_events', privacy.hide_events ? '1' : '0');
      formData.append('members_only', privacy.members_only ? '1' : '0');
      formData.append('instagram', socials.instagram);
      formData.append('strava', socials.strava);
      formData.append('spotify', socials.spotify);
      formData.append('tiktok', socials.tiktok);
      // Send every question, including the ones left blank: an emptied answer
      // has to reach the server to delete its row, and a missing key would read
      // as "unchanged" instead.
      questions.forEach((q) => formData.append(`answer_${q.id}`, answers[q.id] || ''));

      await updateProfile(formData);
      setDirty(false);
      setSaved(true);
      setBarVisible(true);
      setBtnSaved(true);
      setRemovePhoto(false);
      setAvatarFile(null);
    } catch (err) {
      setSaveError(extractApiError(err, 'Chyba při ukládání.'));
      setBarVisible(true);
    } finally {
      setSaving(false);
    }
  };

  const handleAvatar = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setAvatar(reader.result); };
    reader.readAsDataURL(file);
    setAvatarFile(file);
    setRemovePhoto(false);
    markDirty();
  };

  const removeAvatar = () => { setAvatar(null); setAvatarFile(null); setRemovePhoto(true); markDirty(); };

  const setSocial = (key) => (e) => { setSocials((s) => ({ ...s, [key]: e.target.value })); markDirty(); };
  const togglePrivacy = (key) => (next) => { setPrivacy((p) => ({ ...p, [key]: next })); markDirty(); };

  const handleCategories = (next) => { setCategories(next); markDirty(); };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await apiDeleteAccount();
      // The session is already gone server-side; clear it here too so the nav
      // doesn't keep showing a logged-in user who no longer exists.
      setDirty(false);
      await refreshAuth();
      navigate('/', { replace: true });
      toast.success('Účet je smazaný. Body zůstaly na žebříčku anonymně.', { title: 'Sbohem' });
    } catch (err) {
      setDeleteOpen(false);
      reportError('Účet se nepodařilo smazat.', err);
    } finally {
      setDeleting(false);
    }
  };

  useBeforeUnload(dirty);

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

  if (loading) {
    return <div className="gol-form-page editprofile-page"><div style={{ padding: '2rem', textAlign: 'center' }}>Načítání profilu…</div></div>;
  }

  const fullName = `${form.first_name || ''} ${form.last_name || ''}`.trim();
  const avatarInitials = initials(fullName, 'GO');

  return (
    <div className="gol-form-page editprofile-page">
      <div className="ep-stage" aria-hidden="true" />
      <div className="gol-grain" aria-hidden="true" />

      <section className="gol-head">
        <div className="gol-crumb">— <Link to={`/profil/${form.username}`}>Profil</Link> · Upravit —</div>
        <div className="gol-eyebrow">Tvůj kus stránky</div>
        <h1>Upravit profil</h1>
      </section>

      <main className="gol-main">
        {/* 01 · Základy */}
        <section className="gol-section">
          <div className="gol-rule" />
          <div className="gol-card">
            <div className="gol-card-head">
              <div className="gol-sec-eyebrow">— 01 · Základy —</div>
              <h2 className="gol-sec-heading">Kdo <span className="pink">jsi.</span></h2>
              <p className="ep-sec-sub">Tyhle údaje uvidí každý, kdo otevře tvůj profil. E-mail jsou jen pro organizátory.</p>
            </div>
            <div className="gol-grid-2">
              <div className="gol-field">
                <label htmlFor="f-name">Jméno</label>
                <input className="gol-input" id="f-name" value={form.first_name} onChange={setField('first_name')} />
              </div>
              <div className="gol-field">
                <label htmlFor="f-surname">Příjmení</label>
                <input className="gol-input" id="f-surname" value={form.last_name} onChange={setField('last_name')} />
              </div>
              <div className="gol-field">
                <label htmlFor="f-handle">Přezdívka <span className="gol-hint">jen písmena, číslice a _</span></label>
                <div className="gol-input-prefix"><span className="ep-pre">@</span><input className="gol-input" id="f-handle" value={form.username} onChange={setField('username')} autoComplete="username" /></div>
              </div>
              <div className="gol-field">
                <label htmlFor="f-city">Město</label>
                <input className="gol-input" id="f-city" value={form.city} onChange={setField('city')} placeholder="Brno, CZ" />
              </div>
              <div className="gol-field">
                <label htmlFor="f-email">E-mail <span className="gol-hint">jen pro organizátory</span></label>
                <input className="gol-input" id="f-email" type="email" value={form.email} onChange={setField('email')} />
              </div>
            </div>
          </div>
        </section>

        {/* 02 · Avatar */}
        <section className="gol-section">
          <div className="gol-rule" />
          <div className="gol-card ep-avatar-card">
            <div className="gol-card-head">
              <div className="gol-sec-eyebrow">— 02 · Avatar &amp; identita —</div>
              <h2 className="gol-sec-heading">Jak <span className="pink">vypadáš.</span></h2>
              <p className="ep-sec-sub">Tvoje fotka se objeví u tvého jména v leaderboardu, v galerii akcí a vedle každé tvojí RSVP.</p>
            </div>
            <div
              className={`ep-avatar-big${avatar ? ' has-img' : ''}`}
              style={avatar ? { backgroundImage: `url(${avatar})` } : undefined}
            >
              {!avatar && avatarInitials}
            </div>
            <div className="ep-avatar-meta">
              <div className="ep-l">— Profilová fotka —</div>
              <div className="ep-h">{fullName || 'Tvoje jméno'}</div>
              <div className="ep-s">JPG nebo PNG, alespoň 400×400 px. Co tam dáš — z toho ti budou ostatní vařit kávu.</div>
              <div className="ep-avatar-actions">
                <label className="gol-btn primary" htmlFor="avatar-input">Nahrát fotku
                  <input type="file" id="avatar-input" accept="image/*" hidden onChange={handleAvatar} />
                </label>
                <button type="button" className="gol-btn ghost" onClick={removeAvatar}>Odebrat</button>
              </div>
            </div>
          </div>
        </section>

        {/* 03 · Bio */}
        <section className="gol-section">
          <div className="gol-rule" />
          <div className="gol-card">
            <div className="gol-card-head">
              <div className="gol-sec-eyebrow">— 03 · O mně —</div>
              <h2 className="gol-sec-heading">Co o sobě <span className="pink">povíš.</span></h2>
              <p className="ep-sec-sub">Krátký vzkaz, který se objeví v záhlaví tvého profilu. Drž to v jednom dechu — nejvíc 220 znaků.</p>
            </div>
            <div className="gol-field gol-full">
              <label htmlFor="f-bio">Bio</label>
              <textarea
                className="gol-textarea"
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

        {/* 04 · Otázky — same rule as categories: no questions authored in
            admin, no section. An empty heading would read as a broken feature. */}
        {questions.length > 0 && (
          <section className="gol-section">
            <div className="gol-rule" />
            <div className="gol-card">
              <div className="gol-card-head">
                <div className="gol-sec-eyebrow">— 04 · Otázky —</div>
                <h2 className="gol-sec-heading">Pár otázek <span className="pink">na tebe.</span></h2>
                <p className="ep-sec-sub">Nepovinné. Co vyplníš, se objeví na tvém profilu v sekci „O mně“ — co necháš prázdné, se nikde neukáže.</p>
              </div>
              {questions.map((q) => (
                <div key={q.id} className="gol-field gol-full">
                  <label htmlFor={`f-answer-${q.id}`}>{q.text}</label>
                  <textarea
                    className="gol-textarea ep-answer"
                    id={`f-answer-${q.id}`}
                    maxLength={ANSWER_MAX}
                    value={answers[q.id] || ''}
                    onChange={(e) => {
                      const { value } = e.target;
                      setAnswers((a) => ({ ...a, [q.id]: value }));
                      markDirty();
                    }}
                  />
                  <div className="ep-counter">{(answers[q.id] || '').length} / {ANSWER_MAX} znaků</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 05 · Kategorie — hidden entirely when no categories exist to pick */}
        {allCategories.length > 0 && (
          <section className="gol-section">
            <div className="gol-rule" />
            <div className="gol-card">
              <div className="gol-card-head">
                <div className="gol-sec-eyebrow">— 05 · Oblíbené kategorie —</div>
                <h2 className="gol-sec-heading">V čem <span className="pink">jedeš.</span></h2>
                <p className="ep-sec-sub">Vyber až 3 kategorie, ve kterých se nejvíc realizuješ. Pomůže nám doporučit ti akce na míru.</p>
              </div>
              <ChipSelect options={allCategories.map((c) => c.name)} selected={categories} onChange={handleCategories} max={3} />
            </div>
          </section>
        )}

        {/* 06 · Sociální sítě */}
        <section className="gol-section">
          <div className="gol-rule" />
          <div className="gol-card">
            <div className="gol-card-head">
              <div className="gol-sec-eyebrow">— 06 · Sociální sítě —</div>
              <h2 className="gol-sec-heading">Kde tě <span className="pink">najdou.</span></h2>
              <p className="ep-sec-sub">Tyhle odkazy se objeví v sekci „O mně“ na tvém profilu. Nech prázdné, co nechceš sdílet.</p>
            </div>
            <div className="ep-social-rows">
              {SOCIALS.map((s) => (
                <div key={s.key} className={`ep-social-row${socials[s.key].trim() ? ' filled' : ''}`}>
                  <span className="ep-ico">{s.ico}</span>
                  <div className="ep-combo">
                    <span className="ep-pre">{s.pre}</span>
                    <input className="gol-input" value={socials[s.key]} onChange={setSocial(s.key)} placeholder={s.placeholder} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 07 · Soukromí */}
        <section className="gol-section">
          <div className="gol-rule" />
          <div className="gol-card">
            <div className="gol-card-head">
              <div className="gol-sec-eyebrow">— 07 · Soukromí —</div>
              <h2 className="gol-sec-heading">Kdo tě <span className="pink">uvidí.</span></h2>
              <p className="ep-sec-sub">Profil je veřejný, ale tyhle detaily můžeš zamknout.</p>
            </div>
            <div className="gol-toggle-row">
              <div className="gol-txt"><h4>Skrýt body a pořadí</h4><p>Body zmizí z tvého profilu. V žebříčku zůstáváš.</p></div>
              <Switch checked={privacy.hide_pts} onChange={togglePrivacy('hide_pts')} ariaLabel="Skrýt body a pořadí" />
            </div>
            <div className="gol-toggle-row">
              <div className="gol-txt"><h4>Skrýt seznam absolvovaných akcí</h4><p>Tvůj profil ukáže jen highlighty.</p></div>
              <Switch checked={privacy.hide_events} onChange={togglePrivacy('hide_events')} ariaLabel="Skrýt seznam akcí" />
            </div>
            <div className="gol-toggle-row">
              <div className="gol-txt"><h4>Profil pouze pro členy</h4><p>Nepřihlášení návštěvníci tvůj profil vůbec neotevřou.</p></div>
              <Switch checked={privacy.members_only} onChange={togglePrivacy('members_only')} ariaLabel="Profil pouze pro členy" />
            </div>
          </div>
        </section>

        {/* 08 · Danger */}
        <section className="gol-section">
          <div className="gol-rule" />
          <div className="gol-card gol-danger-card">
            <div className="gol-card-head">
              <div className="gol-sec-eyebrow danger">— 08 · Konec hry —</div>
              <h2 className="gol-sec-heading">Něco <span className="pink">extrémního.</span></h2>
              <p className="ep-sec-sub">Tyhle akce jsou nevratné. Mysli si dvakrát.</p>
            </div>
            <div className="gol-toggle-row">
              <div className="gol-txt"><h4>Smazat účet</h4><p>Trvalé. Osobní údaje a nahrané fotky zmizí; body a účast zůstanou v žebříčku anonymně.</p></div>
              <button type="button" className="gol-btn danger" onClick={() => setDeleteOpen(true)}>Smazat účet</button>
            </div>
          </div>
        </section>
      </main>

      <section className="gol-commit-zone">
        <div className="gol-commit-label">— Hotovo? —</div>
        <h2>Uložit změny</h2>
        <div className="gol-commit-row">
          {/* Cancel navigates back → 3D frost; save is an in-place action → round pill. */}
          <Button as="link" to={`/profil/${form.username}`} variant="frost">Zrušit</Button>
          <Button variant="action" size="lg" onClick={handleSave} busy={saving}>{btnSaved ? '✓ Uloženo' : 'Uložit profil'}</Button>
        </div>
        <div className="gol-commit-note">{saveError ? `— Chyba: ${saveError} —` : (dirty ? '— Neuložené změny —' : '— Vše uloženo —')}</div>
      </section>

      <div className={`gol-savebar${barVisible ? ' visible' : ''}`}>
        <div className="gol-savebar-inner">
          <div className={`gol-status${saved ? ' saved' : ''}${saveError ? ' error' : ''}`}><span className="gol-pulse" />{saveError ? saveError : (saved ? 'Vše uloženo' : 'Neuložené změny')}</div>
          <div className="gol-savebar-actions">
            <Button as="link" to={`/profil/${form.username}`} variant="frost" size="sm">Zrušit</Button>
            <Button variant="action" onClick={handleSave} busy={saving}>{btnSaved ? '✓ Uloženo' : 'Uložit změny'}</Button>
          </div>
        </div>
      </div>

      {/* The copy has to match what the code actually does, and what the
          privacy policy promises (§6): personal data goes, points stay on the
          board without a name. Saying "body budou ztraceny" would be a nicer
          sentence and a false one. */}
      <Modal open={deleteOpen} onClose={deleting ? undefined : () => setDeleteOpen(false)} labelledBy="ep-delete-title" width={480}>
        <div className="gol-modal-eyebrow">— Konec hry —</div>
        <h3 id="ep-delete-title" className="gol-modal-title">Smazat účet <span className="pink">natrvalo?</span></h3>
        <p className="gol-modal-text">
          Nevratné. Smažeme tvoje jméno, přezdívku, e-mail, fotku, bio i odkazy
          na sítě — a taky fotky, které jsi nahrál/a do galerie.
        </p>
        <p className="gol-modal-text">
          <strong>Body a účast na akcích zůstanou v žebříčku anonymně</strong>,
          bez vazby na tebe. Výsledky sezóny jsou společný záznam a pořadí
          ostatních dává smysl jen s kompletním polem.
        </p>
        <div className="gol-modal-buttons">
          <Button variant="frost" onClick={() => setDeleteOpen(false)} disabled={deleting}>Zpět</Button>
          <Button variant="action" onClick={confirmDelete} busy={deleting}>Smazat natrvalo</Button>
        </div>
      </Modal>
    </div>
  );
}

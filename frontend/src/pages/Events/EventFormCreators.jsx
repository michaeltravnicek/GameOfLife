import { useState } from 'react';
import { createBadge, createCategory } from '../../services/api';
import { extractApiError } from '../../services/errors';
import { useImagePreview } from '../../hooks/useImagePreview';

/**
 * The "the option I need isn't in the list" half of the event form.
 *
 * Badges and categories used to be creatable only in the Django admin, which
 * meant leaving a half-filled event form to go make one. Both panels post to
 * their admin-only endpoint and hand the created row back to the page, which
 * appends it to the options and selects it — so the author never loses the form
 * state they already typed.
 *
 * Both start collapsed: the common case is picking an existing option, and an
 * always-open upload form would compete with the picker next to it.
 */

/** Badge = artwork + the emblem attendees collect. POST /badges/create/. */
export function NewBadgeForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [scale, setScale] = useState('1');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  // 15 MB matches the server's MAX_UPLOAD_BYTES — a smaller client limit would
  // reject files the API would have taken.
  const art = useImagePreview({ maxSizeMB: 15 });

  const reset = () => {
    setName('');
    setScale('1');
    setDescription('');
    setError(null);
    art.clear();
  };

  const close = () => {
    reset();
    setOpen(false);
  };

  const submit = async () => {
    if (!name.trim()) {
      setError('Zadej název odznaku.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('name', name.trim());
      if (art.file) fd.append('image', art.file);
      fd.append('image_scale', scale || '1');
      fd.append('description', description);
      const badge = await createBadge(fd);
      onCreated(badge);
      close();
    } catch (err) {
      setError(extractApiError(err, 'Odznak se nepodařilo vytvořit.'));
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="ev-inline-add" onClick={() => setOpen(true)}>
        + Nový odznak
      </button>
    );
  }

  return (
    <div className="ev-inline-form">
      <div className="ev-inline-head">Nový odznak</div>
      <div className="gol-field">
        <label htmlFor="nb-name">Název</label>
        <input className="gol-input" id="nb-name" value={name} placeholder="Karaoke King"
               onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="gol-field">
        <label htmlFor="nb-image">Obrázek <span className="gol-hint">PNG, JPG, WEBP, GIF nebo SVG</span></label>
        <input
          className="gol-input"
          id="nb-image"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
          onChange={art.onSelect}
        />
      </div>
      {art.preview && (
        <div className="ev-inline-preview">
          <img src={art.preview} alt="Náhled nového odznaku"
               style={{ transform: `scale(${Number(scale) || 1})` }} />
        </div>
      )}
      <div className="gol-field">
        <label htmlFor="nb-scale">Zvětšení <span className="gol-hint">1 = beze změny</span></label>
        <input className="gol-input" id="nb-scale" type="number" step="0.1" min="0.1" max="5"
               value={scale} onChange={(e) => setScale(e.target.value)} />
      </div>
      <div className="gol-field">
        <label htmlFor="nb-desc">Popis <span className="gol-hint">nepovinné · za co se uděluje</span></label>
        <textarea className="gol-textarea" id="nb-desc" value={description}
                  onChange={(e) => setDescription(e.target.value)} />
      </div>
      {error && <div className="ev-inline-error">{error}</div>}
      <div className="ev-inline-actions">
        <button type="button" className="gol-btn ghost" onClick={close} disabled={saving}>Zrušit</button>
        <button type="button" className="gol-btn primary" onClick={submit} disabled={saving}>
          {saving ? 'Vytvářím…' : 'Vytvořit odznak'}
        </button>
      </div>
    </div>
  );
}

/** Category = the single chip an event is filed under. POST /categories/create/. */
export function NewCategoryForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const close = () => {
    setName('');
    setError(null);
    setOpen(false);
  };

  const submit = async () => {
    if (!name.trim()) {
      setError('Zadej název kategorie.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const category = await createCategory(name.trim());
      onCreated(category);
      close();
    } catch (err) {
      setError(extractApiError(err, 'Kategorii se nepodařilo vytvořit.'));
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="ev-inline-add" onClick={() => setOpen(true)}>
        + Nová kategorie
      </button>
    );
  }

  return (
    <div className="ev-inline-form">
      <div className="ev-inline-head">Nová kategorie</div>
      <div className="gol-field">
        <label htmlFor="nc-name">Název</label>
        <input
          className="gol-input"
          id="nc-name"
          value={name}
          placeholder="Sport"
          maxLength={50}
          onChange={(e) => setName(e.target.value)}
          // Enter would otherwise submit the surrounding page form.
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submit(); } }}
        />
      </div>
      {error && <div className="ev-inline-error">{error}</div>}
      <div className="ev-inline-actions">
        <button type="button" className="gol-btn ghost" onClick={close} disabled={saving}>Zrušit</button>
        <button type="button" className="gol-btn primary" onClick={submit} disabled={saving}>
          {saving ? 'Vytvářím…' : 'Vytvořit kategorii'}
        </button>
      </div>
    </div>
  );
}

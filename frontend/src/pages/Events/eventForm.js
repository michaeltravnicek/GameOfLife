import { useCallback, useState } from 'react';
import { useImagePreview } from '../../hooks/useImagePreview';
import { useBeforeUnload } from '../../hooks/useBeforeUnload';

// Shared plumbing for the create/edit event forms. The two pages differ only in
// their chrome (page head, commit bar, and Edit's load + delete flow); the form
// state, field wiring and the FormData payload are identical and live here.

export const EMPTY_EVENT_FORM = {
  name: '',
  description: '',
  place: '',
  date: '',
  time_tbd: false,
  end_date: '',
  points: '',
  capacity: '',
  rules: '',
  survey_url: '',
  whatsapp_url: '',
  // The logo is the linked badge's artwork — an id, not an upload. '' = no badge.
  badge: '',
  visible_to_users: true,
  visible_to_close: false,
  latitude: '',
  longitude: '',
  checkin_radius: '500',
};

/** Map a loaded API event onto the form state shape (used by the edit page). */
export function eventToForm(event) {
  return {
    name: event.name || '',
    description: event.description || '',
    place: event.place || '',
    // datetime-local inputs want "YYYY-MM-DDTHH:mm" — trim the seconds/zone.
    date: event.date ? event.date.slice(0, 16) : '',
    time_tbd: event.time_tbd ?? false,
    end_date: event.end_date ? event.end_date.slice(0, 16) : '',
    points: event.points || '',
    capacity: event.capacity || '',
    rules: event.rules || '',
    survey_url: event.survey_url || '',
    whatsapp_url: event.whatsapp_url || '',
    badge: event.badge?.id ?? event.badge_id ?? '',
    visible_to_users: event.visible_to_users ?? true,
    visible_to_close: event.visible_to_close ?? false,
    latitude: event.latitude || '',
    longitude: event.longitude || '',
    checkin_radius: event.checkin_radius || '500',
  };
}

/**
 * Build the multipart payload the create/update endpoints expect. `end_date` is
 * always sent (empty string clears it) — the write serializer's
 * BlankableDateTimeField accepts a blank value on both create and update.
 */
export function buildEventFormData(form, { poster, allCategories, categories }) {
  const fd = new FormData();
  fd.append('name', form.name);
  fd.append('description', form.description);
  fd.append('place', form.place);
  if (form.date) fd.append('date', form.date);
  fd.append('time_tbd', form.time_tbd ? '1' : '0');
  fd.append('end_date', form.end_date || '');
  fd.append('points', form.points || 0);
  if (form.capacity) fd.append('capacity', form.capacity);
  fd.append('rules', form.rules);
  fd.append('survey_url', form.survey_url);
  fd.append('whatsapp_url', form.whatsapp_url);
  // Always sent, including as '' — that's how the form clears the badge (and
  // with it the logo). The write serializer maps '' to null.
  fd.append('badge', form.badge ?? '');
  fd.append('visible_to_users', form.visible_to_users ? '1' : '0');
  fd.append('visible_to_close', form.visible_to_close ? '1' : '0');
  if (form.latitude) fd.append('latitude', form.latitude);
  if (form.longitude) fd.append('longitude', form.longitude);
  fd.append('checkin_radius', form.checkin_radius);
  if (poster.file) fd.append('image', poster.file);
  // ChipSelect works in category names; map them back to ids for the API.
  const nameToId = new Map(allCategories.map((c) => [c.name, c.id]));
  categories.forEach((name) => {
    const id = nameToId.get(name);
    if (id != null) fd.append('category', id);
  });
  return fd;
}

/**
 * Owns the mechanical form state both pages share: the field values, dirty
 * tracking (with a leave-page guard), the poster picker, and the category
 * selection. The save/load flow stays in each page since it differs.
 *
 * There is no logo picker: an event's logo is its badge's artwork, chosen by id
 * in the badge section. Uploading artwork means creating a badge.
 */
export function useEventForm() {
  const [form, setForm] = useState(EMPTY_EVENT_FORM);
  const [categories, setCategories] = useState([]);
  const [allCategories, setAllCategories] = useState([]);
  const [badges, setBadges] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const markDirty = useCallback(() => {
    setDirty(true);
    setSaveError(null);
  }, []);

  const poster = useImagePreview({ onChange: markDirty });

  const setField = useCallback((key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
    markDirty();
  }, [markDirty]);

  const handleCategories = useCallback((next) => {
    setCategories(next);
    markDirty();
  }, [markDirty]);

  // A badge/category created from inside the form is always meant for the event
  // being written, so both handlers select what they just added. Inserting into
  // the local list (rather than re-fetching) keeps the half-typed form intact —
  // `byName` mirrors the models' Meta.ordering so the option lands where a
  // reload would put it.
  const handleBadgeCreated = useCallback((badge) => {
    setBadges((prev) => [...prev, badge].sort(byName));
    setForm((f) => ({ ...f, badge: String(badge.id) }));
    markDirty();
  }, [markDirty]);

  const handleCategoryCreated = useCallback((category) => {
    setAllCategories((prev) => [...prev, category].sort(byName));
    // ChipSelect is capped at one category, so this replaces rather than adds.
    setCategories([category.name]);
    markDirty();
  }, [markDirty]);

  // Warn before leaving with unsaved edits (native beforeunload prompt).
  useBeforeUnload(dirty);

  return {
    form, setForm,
    categories, setCategories,
    allCategories, setAllCategories,
    badges, setBadges,
    dirty, saving, setSaving, saveError, setSaveError,
    markDirty, setField, handleCategories,
    handleBadgeCreated, handleCategoryCreated,
    poster,
  };
}

/** Czech-aware name sort, matching Badge/Category `Meta.ordering = ["name"]`. */
function byName(a, b) {
  return a.name.localeCompare(b.name, 'cs');
}

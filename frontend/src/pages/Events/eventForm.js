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
  logo_scale: 1,
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
    logo_scale: event.logo_scale ?? 1,
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
export function buildEventFormData(form, { poster, logo, allCategories, categories }) {
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
  fd.append('logo_scale', form.logo_scale);
  fd.append('visible_to_users', form.visible_to_users ? '1' : '0');
  fd.append('visible_to_close', form.visible_to_close ? '1' : '0');
  if (form.latitude) fd.append('latitude', form.latitude);
  if (form.longitude) fd.append('longitude', form.longitude);
  fd.append('checkin_radius', form.checkin_radius);
  if (poster.file) fd.append('image', poster.file);
  if (logo.file) fd.append('logo', logo.file);
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
 * tracking (with a leave-page guard), the poster/logo image pickers, and the
 * category selection. The save/load flow stays in each page since it differs.
 */
export function useEventForm() {
  const [form, setForm] = useState(EMPTY_EVENT_FORM);
  const [categories, setCategories] = useState([]);
  const [allCategories, setAllCategories] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const markDirty = useCallback(() => {
    setDirty(true);
    setSaveError(null);
  }, []);

  const poster = useImagePreview({ onChange: markDirty });
  const logo = useImagePreview({ onChange: markDirty });

  const setField = useCallback((key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
    markDirty();
  }, [markDirty]);

  const handleCategories = useCallback((next) => {
    setCategories(next);
    markDirty();
  }, [markDirty]);

  // Warn before leaving with unsaved edits (native beforeunload prompt).
  useBeforeUnload(dirty);

  return {
    form, setForm,
    categories, setCategories,
    allCategories, setAllCategories,
    dirty, saving, setSaving, saveError, setSaveError,
    markDirty, setField, handleCategories,
    poster, logo,
  };
}

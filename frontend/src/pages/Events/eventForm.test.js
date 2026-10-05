import { describe, expect, it } from 'vitest';
import { EMPTY_EVENT_FORM, buildEventFormData, eventToForm } from './eventForm';

const CATS = [{ id: 3, name: 'Sport' }, { id: 4, name: 'Kultura' }];
const build = (form, categories = []) =>
  buildEventFormData({ ...EMPTY_EVENT_FORM, name: 'Akce', ...form }, {
    poster: { file: null }, allCategories: CATS, categories,
  });

describe('buildEventFormData', () => {
  // Update is a partial PATCH: a missing key means "unchanged", so a cleared
  // field has to travel as '' or the old value survives the save.
  it('sends cleared capacity, map pin and category as blanks', () => {
    const fd = build({ capacity: '', latitude: '', longitude: '' }, []);
    expect(fd.get('capacity')).toBe('');
    expect(fd.get('latitude')).toBe('');
    expect(fd.get('longitude')).toBe('');
    expect(fd.getAll('category')).toEqual(['']);
    expect(fd.get('badge')).toBe('');
    expect(fd.get('end_date')).toBe('');
  });

  it('sends filled values and one category id', () => {
    const fd = build({ capacity: '30', latitude: 49.19, longitude: 16.6 }, ['Kultura']);
    expect(fd.get('capacity')).toBe('30');
    expect(fd.get('latitude')).toBe('49.19');
    expect(fd.get('longitude')).toBe('16.6');
    expect(fd.getAll('category')).toEqual(['4']);
  });
});

describe('eventToForm', () => {
  it('keeps a zero capacity instead of turning it into a clear', () => {
    expect(eventToForm({ capacity: 0 }).capacity).toBe(0);
    expect(eventToForm({ capacity: null }).capacity).toBe('');
    expect(eventToForm({ latitude: null, longitude: null })).toMatchObject({ latitude: '', longitude: '' });
  });
});

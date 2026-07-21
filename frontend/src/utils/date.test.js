import { describe, it, expect } from 'vitest';
import {
  fmtDate, fmtDateShort, fmtEventDate, fmtTime,
  dayName, monthKey, monthLabel,
} from './date';

// The API shape: a wall-clock time tagged as UTC (Friday 2026-05-15 18:30).
// The formatters read it with the UTC getters, so these assertions hold in any
// machine timezone (no "+2 h in summer" drift).
const ISO = '2026-05-15T18:30:00Z';

describe('date utils (Czech formatting)', () => {
  it('fmtDate renders genitive month name', () => {
    expect(fmtDate(ISO)).toBe('15. května 2026');
  });

  it('fmtDateShort renders dd.mm.yy', () => {
    expect(fmtDateShort(ISO)).toBe('15.05.26');
  });

  it('fmtEventDate renders compact uppercase month', () => {
    expect(fmtEventDate(ISO)).toBe('15. KVĚ 26');
  });

  it('fmtTime pads hours and minutes', () => {
    expect(fmtTime('2026-05-15T08:05:00Z')).toBe('08:05');
  });

  it('dayName returns Czech weekday', () => {
    expect(dayName(ISO)).toBe('Pátek');
  });

  it('monthKey groups by year-month', () => {
    expect(monthKey(ISO)).toBe('2026-05');
  });

  it('monthLabel expands a key back to Czech', () => {
    expect(monthLabel('2026-05')).toBe('Květen 2026');
    expect(monthLabel('unknown')).toBe('Neurčeno');
  });

  it('all formatters tolerate empty input', () => {
    expect(fmtDate(null)).toBe('');
    expect(fmtDateShort('')).toBe('');
    expect(fmtEventDate(undefined)).toBe('—');
    expect(fmtTime('')).toBe('');
    expect(dayName('')).toBe('');
    expect(monthKey(null)).toBe('unknown');
  });
});

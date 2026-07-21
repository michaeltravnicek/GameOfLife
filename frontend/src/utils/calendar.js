import { CapacitorCalendar } from '@ebarooni/capacitor-calendar';
import { isNative } from '../services/platform';
import { publicUrl } from './shareUrl';

const DEFAULT_DURATION_MS = 2 * 60 * 60 * 1000;

function stripHtml(html) {
  const div = document.createElement('div');
  div.innerHTML = html || '';
  return (div.textContent || '').trim();
}

// ICS text fields: escape backslash, comma, semicolon; newlines become \n.
function icsEscape(text) {
  return String(text)
    .replace(/\\/g, '\\\\')
    .replace(/([,;])/g, '\\$1')
    .replace(/\r?\n/g, '\\n');
}

// UTC timestamp in ICS basic format: YYYYMMDDTHHMMSSZ. Used for DTSTAMP (a real
// "now" instant), not for the event's own start/end.
function icsDate(date) {
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

// Event times are wall-clock (stored tagged as UTC — see utils/date.js), so we
// read them back with the UTC getters and emit *floating* local time (no Z): the
// calendar shows "18:00" for every viewer instead of shifting it by their tz.
function icsFloating(date) {
  const p = (n) => String(n).padStart(2, '0');
  return `${date.getUTCFullYear()}${p(date.getUTCMonth() + 1)}${p(date.getUTCDate())}`
    + `T${p(date.getUTCHours())}${p(date.getUTCMinutes())}${p(date.getUTCSeconds())}`;
}

// All-day calendar date (no time) in ICS basic format: YYYYMMDD, from the same
// wall-clock (UTC) components so the day never drifts across a tz offset.
function icsDay(date) {
  const p = (n) => String(n).padStart(2, '0');
  return `${date.getUTCFullYear()}${p(date.getUTCMonth() + 1)}${p(date.getUTCDate())}`;
}

// A local Date carrying the stored wall-clock components — so native calendar
// APIs (which take an epoch instant) also show "18:00" in the device timezone.
function wallClockLocal(date) {
  return new Date(
    date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(),
    date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds(),
  );
}

function buildIcs({ title, location, notes, start, end, uid, allDay }) {
  // All-day: DATE-valued DTSTART/DTEND, and DTEND is exclusive so it points at
  // the day after the start (a single-day all-day event).
  const startLine = allDay
    ? `DTSTART;VALUE=DATE:${icsDay(start)}`
    : `DTSTART:${icsFloating(start)}`;
  const endLine = allDay
    ? `DTEND;VALUE=DATE:${icsDay(new Date(start.getTime() + 24 * 60 * 60 * 1000))}`
    : `DTEND:${icsFloating(end)}`;
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Game of Life//gameofyolo.com//CS',
    'BEGIN:VEVENT',
    `UID:${uid}@gameofyolo.com`,
    `DTSTAMP:${icsDate(new Date())}`,
    startLine,
    endLine,
    `SUMMARY:${icsEscape(title)}`,
    ...(location ? [`LOCATION:${icsEscape(location)}`] : []),
    ...(notes ? [`DESCRIPTION:${icsEscape(notes)}`] : []),
    'END:VEVENT',
    'END:VCALENDAR',
  ];
  // RFC 5545 requires CRLF line endings.
  return lines.join('\r\n') + '\r\n';
}

/**
 * Add a leaderboard event to the user's calendar.
 * Native: opens the OS "new event" editor prefilled (EventKitUI / calendar
 * Intent — write-only access, familiar UI). Web: downloads an .ics file.
 *
 * Expects the API event shape: {name, slug, date, end_date, place, description}.
 */
export async function addEventToCalendar(event) {
  const start = new Date(event.date);
  const end = event.end_date
    ? new Date(event.end_date)
    : new Date(start.getTime() + DEFAULT_DURATION_MS);
  // "Čas upřesníme": the day is set but the start time isn't — add it as an
  // all-day entry instead of pinning a misleading clock time.
  const allDay = !!event.time_tbd;
  const notes = [stripHtml(event.description), publicUrl(`/events/${event.slug}`)]
    .filter(Boolean)
    .join('\n\n');

  if (isNative) {
    await CapacitorCalendar.createEventWithPrompt({
      title: event.name,
      location: event.place || '',
      notes,
      startDate: wallClockLocal(start).getTime(),
      endDate: wallClockLocal(end).getTime(),
      isAllDay: allDay,
    });
    return;
  }

  const ics = buildIcs({
    title: event.name,
    location: event.place || '',
    notes,
    start,
    end,
    uid: event.slug || `event-${start.getTime()}`,
    allDay,
  });
  const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${event.slug || 'akce'}.ics`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

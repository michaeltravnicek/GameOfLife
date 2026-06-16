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

// UTC timestamp in ICS basic format: YYYYMMDDTHHMMSSZ
function icsDate(date) {
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

function buildIcs({ title, location, notes, start, end, uid }) {
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Game of Life//gameofyolo.com//CS',
    'BEGIN:VEVENT',
    `UID:${uid}@gameofyolo.com`,
    `DTSTAMP:${icsDate(new Date())}`,
    `DTSTART:${icsDate(start)}`,
    `DTEND:${icsDate(end)}`,
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
  const notes = [stripHtml(event.description), publicUrl(`/events/${event.slug}`)]
    .filter(Boolean)
    .join('\n\n');

  if (isNative) {
    await CapacitorCalendar.createEventWithPrompt({
      title: event.name,
      location: event.place || '',
      notes,
      startDate: start.getTime(),
      endDate: end.getTime(),
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

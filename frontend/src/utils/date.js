export const MONTHS = [
  'ledna','února','března','dubna','května','června',
  'července','srpna','září','října','listopadu','prosince',
];

export const MONTHS_CZ = [
  'Leden','Únor','Březen','Duben','Květen','Červen',
  'Červenec','Srpen','Září','Říjen','Listopad','Prosinec',
];

export const MONTHS_SHORT = ['LED','ÚNO','BŘE','DUB','KVĚ','ČER','ČVC','SRP','ZÁŘ','ŘÍJ','LIS','PRO'];

export const DAYS_CZ = ['Neděle','Pondělí','Úterý','Středa','Čtvrtek','Pátek','Sobota'];

// Event times are wall-clock: the value entered in the form ("18:00") is stored
// tagged as UTC, so reading it back with the *UTC* getters returns that exact
// wall-clock for every viewer — no browser-timezone shift. Do NOT switch these
// to the local getters (getHours/getDate/…): that reintroduces the "+2 h in
// summer" (CEST) display bug.

export function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getUTCDate()}. ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

export function fmtDateShort(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${String(d.getUTCDate()).padStart(2,'0')}.${String(d.getUTCMonth()+1).padStart(2,'0')}.${String(d.getUTCFullYear()).slice(2)}`;
}

// Compact event-list date, e.g. "12. KVĚ 25". Shared by the profile/player lists.
export function fmtEventDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getUTCDate()}. ${MONTHS_SHORT[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`;
}

export function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getUTCHours().toString().padStart(2,'0')}:${d.getUTCMinutes().toString().padStart(2,'0')}`;
}

export function dayName(iso) {
  if (!iso) return '';
  return DAYS_CZ[new Date(iso).getUTCDay()];
}

export function monthKey(iso) {
  if (!iso) return 'unknown';
  const d = new Date(iso);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`;
}

export function monthLabel(key) {
  if (key === 'unknown') return 'Neurčeno';
  const [y, m] = key.split('-');
  return `${MONTHS_CZ[Number(m)-1]} ${y}`;
}

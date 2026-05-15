export const MONTHS = [
  'ledna','února','března','dubna','května','června',
  'července','srpna','září','října','listopadu','prosince',
];

export const MONTHS_CZ = [
  'Leden','Únor','Březen','Duben','Květen','Červen',
  'Červenec','Srpen','Září','Říjen','Listopad','Prosinec',
];

export const DAYS_CZ = ['Neděle','Pondělí','Úterý','Středa','Čtvrtek','Pátek','Sobota'];

export function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getDate()}. ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function fmtDateShort(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getFullYear()).slice(2)}`;
}

export function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
}

export function dayName(iso) {
  if (!iso) return '';
  return DAYS_CZ[new Date(iso).getDay()];
}

export function monthKey(iso) {
  if (!iso) return 'unknown';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
}

export function monthLabel(key) {
  if (key === 'unknown') return 'Neurčeno';
  const [y, m] = key.split('-');
  return `${MONTHS_CZ[Number(m)-1]} ${y}`;
}

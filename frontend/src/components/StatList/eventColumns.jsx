import { fmtEventDate } from '../../utils/date';

/**
 * Shared event-row arrangement (rank · category · name/place · date · points)
 * used by both the profile and player event lists via <StatList>. Cell styling
 * lives in StatList.css under the `ev-*` classes; grid columns under
 * `.stat-list.ev-grid`. Pair with `className={EVENT_LIST_CLASS}`.
 *
 * Rows need: { name, place, date, category?: { name }, pts | points }.
 */
export const EVENT_COLUMNS = [
  { key: 'rk', className: 'ev-rk', render: (_e, i) => String(i + 1).padStart(2, '0') },
  { key: 'cat', className: 'ev-cat', render: (e) => e.category?.name || 'Akce' },
  {
    key: 'info',
    className: 'ev-info',
    render: (e) => (
      <>
        <div className="nm">{e.name}</div>
        {e.place && <div className="loc">{e.place}</div>}
      </>
    ),
  },
  { key: 'dt', className: 'ev-dt', render: (e) => fmtEventDate(e.date) },
  { key: 'pts', className: 'ev-pt', render: (e) => <>+{e.pts ?? e.points}<span className="u">pts</span></> },
];

// Ticket skin (dark brown2 panel; consumer supplies the dashed frame) + the
// shared event grid template.
export const EVENT_LIST_CLASS = 'ticket ev-grid';

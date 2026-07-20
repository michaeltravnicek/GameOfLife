import { fmtEventDate } from '../../utils/date';

/**
 * Shared row arrangement for the ticket lists (rank · category · name/place ·
 * date · points) used by the profile and player event lists, and by the
 * event-detail attendance/RSVP lists, via <TicketList>.
 *
 * Cell styling lives in StatList.css under the `ev-*` classes; pair with
 * `className={EVENT_LIST_CLASS}`.
 *
 * Rows need: { name, place, date, category?: { name }, pts | points }.
 */

// One definition per column: its cell class, its default renderer, and the
// grid width it occupies. Keeping the width here is what lets `eventList()`
// build a matching grid-template for any subset.
const COLUMNS = {
  rk: {
    className: 'ev-rk',
    width: '52px',
    render: (_row, i) => String(i + 1).padStart(2, '0'),
  },
  // No fallback label — rows without a category get no chip (the cell
  // collapses via the .ev-cat:empty rule in StatList.css).
  cat: {
    className: 'ev-cat',
    width: '90px',
    render: (row) => row.category?.name || null,
  },
  info: {
    className: 'ev-info',
    width: '1fr',
    render: (row) => (
      <>
        <div className="nm">{row.name}</div>
        {row.place && <div className="loc">{row.place}</div>}
      </>
    ),
  },
  dt: {
    className: 'ev-dt',
    width: '110px',
    render: (row) => fmtEventDate(row.date),
  },
  pts: {
    className: 'ev-pt',
    width: '90px',
    render: (row) => <>+{row.pts ?? row.points}<span className="u">pts</span></>,
  },
};

const DEFAULT_ORDER = ['rk', 'cat', 'info', 'dt', 'pts'];

/**
 * Build the `columns` + `gridTemplate` pair for a ticket list.
 *
 *   include  : column keys to show, in order (default: all five)
 *   render   : { key: (row, i) => Node } — swap a column's renderer while
 *              keeping its cell class and width (e.g. a person's name in the
 *              `info` slot, an editable field in `pts`)
 *   width    : { key: cssWidth } — override a column's grid width
 *   extra    : additional { key, className?, width?, render } columns appended
 *              after the included ones (e.g. a row action button)
 *
 * Returns `{ columns, gridTemplate, className }` — spread straight into
 * <TicketList {...eventList({ ... })} rows={…} />.
 */
export function eventList({ include = DEFAULT_ORDER, render = {}, width = {}, extra = [] } = {}) {
  const picked = include.map((key) => {
    const base = COLUMNS[key];
    if (!base) throw new Error(`eventList: unknown column "${key}"`);
    return {
      key,
      className: base.className,
      render: render[key] || base.render,
      width: width[key] || base.width,
    };
  });

  const all = [...picked, ...extra.map((c) => ({ width: 'auto', ...c }))];

  return {
    className: EVENT_LIST_CLASS,
    columns: all.map(({ key, className, render: r }) => ({ key, className, render: r })),
    gridTemplate: all.map((c) => c.width).join(' '),
  };
}

// The full five-column event row — what the profile and player pages show.
export const EVENT_COLUMNS = DEFAULT_ORDER.map((key) => ({
  key,
  className: COLUMNS[key].className,
  render: COLUMNS[key].render,
}));

// The shared event grid skin (the ticket-panel look is StatList's base).
export const EVENT_LIST_CLASS = 'ev-grid';

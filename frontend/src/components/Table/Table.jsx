import './Table.css';

/**
 * Sortable data table styled to match the leaderboard design.
 *
 * columns : Array<{
 *   key      : string,
 *   label    : string,
 *   sortable?: bool,
 *   align?   : 'left' | 'right' | 'center',
 *   render?  : (value, row) => ReactNode,
 * }>
 *
 * rows      : Array<object>
 * sortKey   : string | null    — controlled sort column
 * sortDir   : 'asc' | 'desc'  — controlled sort direction
 * onSort    : (key) => void    — called when a sortable header is clicked
 * emptyText : string           — shown when rows is empty
 */
export default function Table({
  columns = [],
  rows = [],
  sortKey = null,
  sortDir = 'asc',
  onSort,
  emptyText = 'Žádná data.',
  className = '',
}) {
  return (
    <div className={`data-table-wrap${className ? ' ' + className : ''}`}>
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => {
              const isActive = sortKey === col.key;
              const alignClass = col.align === 'right' ? 'col-right' : col.align === 'center' ? 'col-center' : '';
              return (
                <th
                  key={col.key}
                  className={[
                    col.sortable ? 'sortable' : '',
                    isActive ? 'sort-active' : '',
                    isActive && sortDir === 'desc' ? 'sort-desc' : '',
                    alignClass,
                  ].filter(Boolean).join(' ')}
                  onClick={col.sortable && onSort ? () => onSort(col.key) : undefined}
                >
                  {col.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="data-table-empty">{emptyText}</td>
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr key={row.id ?? ri}>
                {columns.map((col) => {
                  const alignClass = col.align === 'right' ? 'col-right' : col.align === 'center' ? 'col-center' : '';
                  return (
                    <td key={col.key} className={alignClass}>
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

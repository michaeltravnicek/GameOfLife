import { Link } from 'react-router-dom';
import './StatList.css';

/**
 * Leaderboard-style list: a blue grain-textured box with a dashed inset border
 * and dashed-separated rows. Same DOM structure as the leaderboard's `.list`,
 * so it stays visually identical across pages — only the columns change.
 *
 * columns      : Array<{
 *   key       : string,
 *   className? : string,                 — cell class for per-page styling
 *   render?    : (row, index) => Node,   — defaults to row[key]
 * }>
 * rows         : Array<object>
 * gridTemplate : CSS grid-template-columns string for each row
 * rowKey?      : (row, index) => key
 * rowLink?     : (row) => string | null  — renders the row as a <Link> when set
 * rowClass?    : (row, index) => string  — extra class per row (e.g. 'future'/'past')
 * emptyText?   : string
 */
export default function StatList({
  columns = [],
  rows = [],
  gridTemplate,
  rowKey,
  rowLink,
  rowClass,
  emptyText = 'Žádná data.',
  className = '',
}) {
  return (
    <div className={`stat-list${className ? ' ' + className : ''}`}>
      <div className="stat-list-inner">
        {rows.length === 0 ? (
          <div className="stat-list-empty">{emptyText}</div>
        ) : (
          rows.map((row, i) => {
            const cells = columns.map((col) => (
              <div key={col.key} className={`stat-cell${col.className ? ' ' + col.className : ''}`}>
                {col.render ? col.render(row, i) : row[col.key]}
              </div>
            ));
            const style = gridTemplate ? { gridTemplateColumns: gridTemplate } : undefined;
            const key = rowKey ? rowKey(row, i) : (row.id ?? i);
            const to = rowLink ? rowLink(row) : null;
            const extra = rowClass ? rowClass(row, i) : '';
            const base = `stat-row${extra ? ' ' + extra : ''}`;
            return to ? (
              <Link key={key} to={to} className={`${base} clickable`} style={style}>{cells}</Link>
            ) : (
              <div key={key} className={base} style={style}>{cells}</div>
            );
          })
        )}
      </div>
    </div>
  );
}

import './LoadMore.css';

/**
 * The centred "Načíst další" pill under a paginated list.
 * Pairs with services/usePaginatedQuery: `onClick={loadMore}`, `busy={loadingMore}`.
 *
 * remaining : number — appended in brackets when known ("Načíst další (12)")
 */
export default function LoadMore({ onClick, busy = false, remaining, label = 'Načíst další', busyLabel = 'Načítám…' }) {
  const text = busy ? busyLabel : remaining != null ? `${label} (${remaining})` : label;
  return (
    <div className="load-more">
      <button type="button" className="gol-pill" onClick={onClick} disabled={busy}>
        {text}
      </button>
    </div>
  );
}

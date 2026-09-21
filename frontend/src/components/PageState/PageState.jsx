import './PageState.css';

/**
 * The one way a page says "loading", "nothing here", or "that failed".
 *
 * Every list page had its own empty-state rule and most pages hand-rolled a
 * loading/error line as an inline style. Same words, thirteen looks. This is
 * the events page's version (the only one that told loading, empty and error
 * apart), promoted.
 *
 * kind       : 'loading' | 'empty' | 'error'
 * text       : the sentence, in Czech
 * onRetry    : error only — renders a "Zkusit znovu" pill that calls it
 * busy       : the retry is in flight (pill disabled, label swaps)
 * compact    : inside a card — 44px padding instead of 60
 * fill       : whole-page state — centred in at least 60vh
 */
export default function PageState({
  kind = 'empty',
  text,
  onRetry,
  busy = false,
  retryLabel = 'Zkusit znovu',
  busyLabel = 'Načítám…',
  compact = false,
  fill = false,
  className = '',
}) {
  const classes = ['page-state', `page-state--${kind}`, compact && 'page-state--compact', fill && 'page-state--fill', className]
    .filter(Boolean)
    .join(' ');
  return (
    <div className={classes} role={kind === 'error' ? 'alert' : 'status'}>
      {kind === 'loading' && <span className="gol-spinner" aria-hidden="true" />}
      <p className="page-state-text">{text}</p>
      {kind === 'error' && onRetry && (
        <button type="button" className="gol-pill" onClick={onRetry} disabled={busy}>
          {busy ? busyLabel : retryLabel}
        </button>
      )}
    </div>
  );
}

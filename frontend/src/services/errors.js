import { toast } from '../components/Toast/ToastProvider';

/**
 * Pull a human-readable message out of an axios error, normalizing the three
 * response shapes the API uses:
 *   - `{ error: "..." }`             (single message — most endpoints)
 *   - `{ errors: { field: [...] } }` (field errors — register)
 *   - `{ field: [...] }`             (DRF serializer validation — bare field keys,
 *                                     incl. `non_field_errors`)
 * Falls back to `fallback`, then a generic Czech message.
 */
export function extractApiError(err, fallback) {
  const data = err?.response?.data;
  if (data?.error) return data.error;
  const fields = data?.errors || (data && typeof data === 'object' ? data : null);
  if (fields) {
    const first = Object.values(fields)[0];
    if (Array.isArray(first) && first.length) return String(first[0]);
    if (typeof first === 'string' && first) return first;
  }
  return fallback || 'Něco se nepovedlo.';
}

/**
 * The one way to surface a failed action: every catch block funnels through
 * this — never `alert()` or a silent `.catch(() => {})`.
 *
 *   apiCall().catch(reportError('Nepodařilo se uložit změny.'));   // as a handler
 *   reportError('Nepodařilo se uložit změny.', err);                // in try/catch
 *
 * Shows an error toast with the server's message when there is one, else
 * `fallback`; logs the error in dev. `title` defaults to "Chyba".
 */
export function reportError(fallback, errMaybe, { title = 'Chyba' } = {}) {
  const handler = (err) => {
    const msg = extractApiError(err, fallback);
    toast.error(msg, { title });
    if (import.meta.env.DEV) {
      console.error(err);
    }
  };
  if (errMaybe !== undefined) {
    handler(errMaybe);
    return undefined;
  }
  return handler;
}

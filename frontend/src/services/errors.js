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
 * The one and only way to surface a failed action to the user.
 *
 * RULE: every catch block in this codebase MUST funnel through this helper.
 * No `alert()`, no silent `.catch(() => {})`, no per-page improvisation.
 *
 * Two usage shapes:
 *
 *   // 1. As a Promise .catch handler (most common):
 *   apiCall().catch(reportError('Nepodařilo se uložit změny.'));
 *
 *   // 2. Inside try/catch:
 *   try {
 *     await apiCall();
 *   } catch (err) {
 *     reportError('Nepodařilo se uložit změny.', err);
 *   }
 *
 * Behavior:
 *   - Shows an error toast.
 *   - Uses the server-provided `error` field from the response if present
 *     (axios path: err.response.data.error), otherwise the fallback string.
 *   - In dev: logs the full error to the console for debugging.
 *
 * `title` defaults to "Chyba" — override per-domain when useful.
 */
export function reportError(fallback, errMaybe, { title = 'Chyba' } = {}) {
  const handler = (err) => {
    const msg = extractApiError(err, fallback);
    toast.error(msg, { title });
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.error(err);
    }
  };
  if (errMaybe !== undefined) {
    handler(errMaybe);
    return undefined;
  }
  return handler;
}

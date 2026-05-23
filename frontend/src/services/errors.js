import { toast } from '../components/Toast/ToastProvider';

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
    const serverMsg = err?.response?.data?.error;
    const msg = serverMsg || fallback || 'Něco se nepovedlo.';
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

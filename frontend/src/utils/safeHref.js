/**
 * Guard an outbound link before it becomes an <a href>.
 *
 * `whatsapp_url` and `survey_url` arrive from the API as whatever an admin
 * pasted into the event form. The backend's URLField already refuses
 * `javascript:` and `data:` on the way in, so this is the second lock, not the
 * first: a future field added as a plain CharField, an admin-panel edit that
 * bypasses the serializer, or a compromised admin account would otherwise put
 * a script URL behind "Otevřít formulář ↗" for every member who joins.
 *
 * Only http(s) qualifies — nothing else has any business in an outbound link
 * here. Returns null for anything that fails, so the caller can drop the link
 * rather than render one that goes nowhere.
 */
export function safeExternalHref(raw) {
  if (typeof raw !== 'string') return null;
  let url;
  try {
    url = new URL(raw.trim());
  } catch {
    return null;
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
  return url.toString();
}

export default safeExternalHref;

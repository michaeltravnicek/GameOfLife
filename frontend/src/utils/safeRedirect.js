/**
 * Validate a post-login redirect target before handing it to `navigate()`.
 *
 * This is the frontend's `url_has_allowed_host_and_scheme()`. The login and
 * register pages read `?from=` straight out of the address bar, exactly like
 * Django's `LoginView` reads `?next=`, and an attacker controls that value:
 * mail a member `/prihlasit?from=<somewhere else>` and they see the real site,
 * the real TLS certificate and the real login form — then land on a lookalike
 * that asks them to "log in again".
 *
 * React Router is *supposed* to refuse an off-site target, but versions before
 * 7.15.1 let a backslash through (GHSA-wrjc-x8rr-h8h6): `\/\/evil.com` reads as
 * an ordinary path, and the browser then treats `\` as `/`, so it resolves to
 * `//evil.com`. The dependency is patched, but the check lives here too because
 * it is the half that stays correct across router upgrades — the router's job
 * is routing, not deciding whom we trust.
 *
 * The only legitimate producer of `?from=` is the 401 interceptor in
 * services/api.js, which builds it from `window.location.pathname + search`.
 * That always has exactly one leading slash, so nothing real is ever rejected.
 */

// One leading slash and no backslash anywhere. That rejects protocol-relative
// targets (`//evil.com`), the backslash variants the advisory is about, and
// absolute URLs of any scheme (`https://…`, `javascript:…`) — none of which
// can appear in a genuine in-app path.
const IN_APP_PATH = /^\/(?!\/)/;

export function safeRedirect(to, fallback) {
  if (typeof to !== 'string') return fallback;
  if (!IN_APP_PATH.test(to)) return fallback;
  if (to.includes('\\')) return fallback;
  return to;
}

export default safeRedirect;

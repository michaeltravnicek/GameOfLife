import { Link } from 'react-router-dom';

// Inline SVG rather than a hosted asset: Google's mark must keep its exact four
// brand colours, and an <img> from gstatic would need a CSP img-src entry plus a
// network round trip for about a kilobyte.
function GoogleMark() {
  return (
    <svg className="auth-google-mark" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24s.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

/**
 * Google sign-in entry point, shared by the login and registration cards.
 *
 * The link is a plain <a href>, deliberately NOT a React Router <Link>. This has
 * to be a real navigation to the server: <Link> would push a client route the
 * SPA has no page for, and the request would never reach Django. Django then
 * redirects to Google, handles the callback, sets the ordinary session cookie,
 * and sends the browser home — React reboots already logged in, with no token
 * and no change to the auth model.
 *
 * `showConsent` renders the privacy notice. The password form carries an
 * explicit consent checkbox; this flow has no form to put one on, so the notice
 * lives on the button and SocialAccountAdapter.save_user records the consent
 * server-side. Keep the two in step — dropping this text would mean recording an
 * agreement nobody was shown.
 */
export default function GoogleSignInButton({ label = 'Pokračovat přes Google', showConsent = true }) {
  return (
    <>
      <div className="auth-or"><span>nebo</span></div>
      <a href="/accounts/google/login/?process=login" className="auth-google">
        <GoogleMark />
        <span>{label}</span>
      </a>
      {showConsent && (
        <p className="auth-google-note">
          Pokračováním souhlasíš se{' '}
          <Link to="/ochrana-osobnich-udaju">zásadami zpracování osobních údajů</Link>.
        </p>
      )}
    </>
  );
}

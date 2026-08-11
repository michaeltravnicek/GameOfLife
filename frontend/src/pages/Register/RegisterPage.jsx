import { useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { toast } from '../../components/Toast/ToastProvider';
import FormInput from '../../components/FormInput/FormInput';
import Button from '../../components/Button/Button';
import { extractApiError } from '../../services/errors';
import GoogleSignInButton from '../../components/GoogleSignInButton/GoogleSignInButton';
import { safeRedirect } from '../../utils/safeRedirect';
import '../Login/AuthPage.css';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [first, setFirst] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [gdpr, setGdpr] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [busy, setBusy] = useState(false);

  // API shape: { errors: { field: [messages] } } (Django form errors; non-field
  // messages arrive under "__all__"). Flatten to one message per field.
  const apiFieldErrors = (err) => {
    const errs = err?.response?.data?.errors;
    if (!errs) return {};
    return Object.fromEntries(
      Object.entries(errs).map(([k, v]) => [k, Array.isArray(v) ? v[0] : String(v)]),
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});
    if (pw !== pw2) {
      setFieldErrors({ password2: 'Hesla se neshodují.' });
      return;
    }
    // Checked here for a fast, friendly message; the server enforces it too
    // (CustomUserCreationForm.gdpr_consent), so posting straight to the API
    // cannot create an account without a recorded consent.
    if (!gdpr) {
      setFieldErrors({ gdpr_consent: 'Bez souhlasu tě bohužel nemůžeme zaregistrovat.' });
      return;
    }
    setBusy(true);
    try {
      const u = await register({
        first_name: first,
        username,
        email,
        password1: pw,
        password2: pw2,
        gdpr_consent: gdpr,
      });
      // The name looked like an existing unclaimed player. Set expectations —
      // the points aren't lost, an admin just has to confirm the link. We never
      // say whose points, so this leaks nothing about other people.
      if (u.possible_link) {
        toast.info(
          'Vypadá to, že už u nás máš body z dřívějška. Přiřadíme ti je, jakmile tě ověříme.',
          { title: 'Možná už tě známe', duration: 9000 },
        );
      }
      // `from` may arrive as router state (in-app) or a ?from= query param
      // (api.js 401 interceptor redirect) — honour either, but only after
      // safeRedirect: the query param comes from the URL, so it is exactly as
      // trustworthy as whoever sent the member the link.
      const from = location.state?.from || searchParams.get('from');
      navigate(safeRedirect(from, `/profil/${u.username}`), { replace: true });
    } catch (err) {
      const fields = apiFieldErrors(err);
      setFieldErrors(fields);
      // Generic box only for non-field failures (or when nothing maps to a field).
      const fieldKeys = Object.keys(fields).filter((k) => k !== '__all__');
      if (fields.__all__ || !fieldKeys.length) {
        setError(fields.__all__ || extractApiError(err, 'Registrace selhala.'));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    // auth-poster — shared look of all auth pages: photo bg + one opaque
    // poster card holding the page name; inputs are mini homepage-event-card
    // tickets (AuthPage.css).
    <div className="auth-page auth-poster">
      <div className="stage" aria-hidden="true" />

      <section className="auth-container">
        <div className="auth-card wide">
          <div className="auth-card-inner">
            <div className="auth-card-tag">Game of Life · Sezóna 2025/26</div>
            <h2 className="auth-card-title">Registrace</h2>
            <div className="auth-card-sub">Nový hráč · pár údajů a jsi ve hře</div>
            <div className="auth-divider" />
            <form onSubmit={handleSubmit} noValidate>
              <FormInput
                id="reg-first" label="Jméno" type="text"
                placeholder="Jan" autoComplete="given-name"
                value={first} onChange={(e) => setFirst(e.target.value)} required
                errorText={fieldErrors.first_name}
              />
              <FormInput
                id="reg-username" label="Přezdívka" type="text"
                placeholder="honzic" autoComplete="username"
                value={username} onChange={(e) => setUsername(e.target.value)} required
                errorText={fieldErrors.username}
              />
              <FormInput
                id="reg-email" label="E-mail" type="email"
                placeholder="jan@example.com" autoComplete="email"
                value={email} onChange={(e) => setEmail(e.target.value)} required
                errorText={fieldErrors.email}
              />
              <FormInput
                id="reg-pw" label="Heslo" type="password"
                placeholder="········" autoComplete="new-password"
                value={pw} onChange={(e) => setPw(e.target.value)} required
                errorText={fieldErrors.password1}
              />
              <FormInput
                id="reg-pw2" label="Potvrdit heslo" type="password"
                placeholder="········" autoComplete="new-password"
                value={pw2} onChange={(e) => setPw2(e.target.value)} required
                errorText={fieldErrors.password2}
              />
              {/* Consent lives immediately above the submit button so it is
                  read at the moment of deciding, not skimmed past earlier.
                  The policy opens in a new tab — navigating away here would
                  discard everything already typed into the form. */}
              <div className="auth-consent">
                <label className="auth-consent-row" htmlFor="reg-gdpr">
                  <input
                    id="reg-gdpr"
                    type="checkbox"
                    checked={gdpr}
                    onChange={(e) => setGdpr(e.target.checked)}
                    aria-describedby={fieldErrors.gdpr_consent ? 'reg-gdpr-err' : undefined}
                  />
                  <span>
                    Souhlasím se zpracováním osobních údajů a beru na vědomí{' '}
                    <Link to="/ochrana-osobnich-udaju" target="_blank" rel="noopener noreferrer">
                      zásady ochrany osobních údajů
                    </Link>.
                  </span>
                </label>
                {fieldErrors.gdpr_consent && (
                  <div className="auth-consent-err" id="reg-gdpr-err" role="alert">
                    {fieldErrors.gdpr_consent}
                  </div>
                )}
              </div>
              {error && <div className="auth-error">{error}</div>}
              <Button type="submit" variant="nav" size="lg" busy={busy} className="pts-btn-wrap">
                {busy ? 'Registruji…' : <>Registrovat se <span className="arr" aria-hidden="true" /></>}
              </Button>
            </form>

            <GoogleSignInButton label="Zaregistrovat se přes Google" />

            <p className="auth-foot">Už máš účet? <Link to={{ pathname: '/prihlasit', search: location.search }} state={location.state}>Přihlásit se</Link></p>
          </div>
        </div>
      </section>
    </div>
  );
}

import { useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import FormInput from '../../components/FormInput/FormInput';
import Button from '../../components/Button/Button';
import { extractApiError } from '../../services/errors';
import GoogleSignInButton from '../../components/GoogleSignInButton/GoogleSignInButton';
import { safeRedirect } from '../../utils/safeRedirect';
import './AuthPage.css';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [identifier, setIdentifier] = useState('');
  const [pw, setPw] = useState('');
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const u = await login(identifier, pw, remember);
      // `from` arrives either as router state (in-app redirects) or as a
      // ?from= query param (the api.js 401 interceptor redirects via
      // window.location, which can't carry router state). The query param is
      // attacker-controlled, so it goes through safeRedirect — an off-site
      // target here would bounce a member who *just* typed their password.
      const from = location.state?.from || searchParams.get('from');
      navigate(safeRedirect(from, `/profil/${u.username}`), { replace: true });
    } catch (err) {
      setError(extractApiError(err, 'Přihlášení selhalo.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page auth-poster">
      <div className="stage" aria-hidden="true" />

      <section className="auth-container">
        <div className="auth-card">
          <div className="auth-card-inner">
            <div className="auth-card-tag">Game of Life · Sezóna 2025/26</div>
            <h2 className="auth-card-title">Přihlášení</h2>
            <div className="auth-card-sub">Hráč · zadej svoje údaje</div>
            <div className="auth-divider" />
            <form onSubmit={handleSubmit} noValidate>
              <FormInput
                id="login-id"
                label="Přezdívka nebo e-mail"
                type="text"
                placeholder="jannovak nebo jan@example.com"
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
              />
              <FormInput
                id="login-pw"
                label="Heslo"
                type="password"
                placeholder="········"
                autoComplete="current-password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                required
                rightSlot={<Link to="/zapomenute-heslo" className="forgot">Zapomenuté heslo?</Link>}
              />
              {error && <div className="auth-error">{error}</div>}
              <label className="remember-row">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                <span>Zůstat přihlášen</span>
              </label>
              <Button type="submit" variant="nav" size="lg" busy={busy} className="pts-btn-wrap">
                {busy ? 'Přihlašuji…' : <>Přihlásit se <span className="arr" aria-hidden="true" /></>}
              </Button>
            </form>

            <GoogleSignInButton />

            <p className="auth-foot">Nemáš účet? <Link to={{ pathname: '/registrace', search: location.search }} state={location.state}>Zaregistrovat se</Link></p>
          </div>
        </div>
      </section>
    </div>
  );
}

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './AuthPage.css';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
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
      const u = await login(identifier, pw);
      navigate(`/profil/${u.username}`);
    } catch (err) {
      setError(err.response?.data?.error || 'Přihlášení selhalo.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="stage" />
      <div className="grain" />
      <section className="hero-section">
        <div className="hero-inner">
          <div className="hero-eyebrow">Game of Life · Sezóna 2025/26</div>
          <h1 className="hero-title">Dobrodružství čeká!</h1>
          <p className="hero-sub">Pokračuj tam, kde jsi skončil.</p>
        </div>
      </section>

      <section className="auth-container">
        <div className="auth-card">
          <div className="auth-card-bg" />
          <div className="auth-card-inner">
            <div className="auth-card-tag">Game of Life</div>
            <h2 className="auth-card-title">Přihlášení</h2>
            <div className="auth-card-sub">Hráč · zadej svoje údaje</div>
            <div className="auth-divider" />
            <form onSubmit={handleSubmit} noValidate>
              <div className="form-group">
                <label htmlFor="login-id">Telefon nebo e-mail</label>
                <input
                  id="login-id"
                  type="text"
                  placeholder="731 005 976 nebo jan@example.com"
                  autoComplete="username"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="login-pw">Heslo</label>
                <a href="#" className="forgot">Zapomenuté heslo?</a>
                <input
                  id="login-pw"
                  type="password"
                  placeholder="········"
                  autoComplete="current-password"
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                  required
                />
              </div>
              {error && <div className="auth-error">{error}</div>}
              <label className="remember-row">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                <span>Zůstat přihlášen</span>
              </label>
              <button type="submit" className="pts-btn" disabled={busy}>
                {busy ? 'Přihlašuji…' : 'Přihlásit se →'}
              </button>
            </form>
            <p className="auth-foot">Nemáš účet? <Link to="/registrace">Zaregistrovat se</Link></p>
          </div>
        </div>
      </section>
    </div>
  );
}

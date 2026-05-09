import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import '../Login/AuthPage.css';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [first, setFirst] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (pw !== pw2) {
      setError('Hesla se neshodují.');
      return;
    }
    setBusy(true);
    try {
      const u = await register({
        first_name: first,
        email,
        phone,
        password1: pw,
        password2: pw2,
      });
      navigate(`/profil/${u.username}`);
    } catch (err) {
      const errs = err.response?.data?.errors;
      if (errs) {
        const first = Object.values(errs)[0];
        setError(Array.isArray(first) ? first[0] : String(first));
      } else {
        setError('Registrace selhala.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <section className="hero-section">
        <div className="hero-bg register-bg" />
        <div className="hero-overlay" />
        <div className="hero-inner">
          <div className="hero-eyebrow">Game of Life · Sezóna 2025/26</div>
          <h1 className="hero-title">Začni hrát život naplno!</h1>
          <p className="hero-sub">Vytvoř si účet, sbírej body a hraj naplno.</p>
        </div>
      </section>

      <section className="auth-container">
        <div className="auth-card wide">
          <div className="auth-card-bg" />
          <div className="auth-card-inner">
            <div className="auth-card-tag">Game of Life</div>
            <h2 className="auth-card-title">Registrace</h2>
            <div className="auth-card-sub">Nový hráč · pár údajů a jsi ve hře</div>
            <div className="auth-divider" />
            <form onSubmit={handleSubmit} noValidate>
              <div className="form-group">
                <label htmlFor="reg-first">Jméno</label>
                <input
                  id="reg-first" type="text" placeholder="Jan" autoComplete="given-name"
                  value={first} onChange={(e) => setFirst(e.target.value)} required
                />
              </div>
              <div className="form-group">
                <label htmlFor="reg-phone">Telefon (9 číslic)</label>
                <input
                  id="reg-phone" type="tel" placeholder="731 005 976" autoComplete="tel"
                  value={phone} onChange={(e) => setPhone(e.target.value)} required
                />
              </div>
              <div className="form-group">
                <label htmlFor="reg-email">E-mail</label>
                <input
                  id="reg-email" type="email" placeholder="jan@example.com" autoComplete="email"
                  value={email} onChange={(e) => setEmail(e.target.value)} required
                />
              </div>
              <div className="form-group">
                <label htmlFor="reg-pw">Heslo</label>
                <input
                  id="reg-pw" type="password" placeholder="········" autoComplete="new-password"
                  value={pw} onChange={(e) => setPw(e.target.value)} required
                />
              </div>
              <div className="form-group">
                <label htmlFor="reg-pw2">Potvrdit heslo</label>
                <input
                  id="reg-pw2" type="password" placeholder="········" autoComplete="new-password"
                  value={pw2} onChange={(e) => setPw2(e.target.value)} required
                />
              </div>
              {error && <div className="auth-error">{error}</div>}
              <button type="submit" className="pts-btn" disabled={busy}>
                {busy ? 'Registruji…' : 'Registrovat se →'}
              </button>
            </form>
            <p className="auth-foot">Už máš účet? <Link to="/prihlasit">Přihlásit se</Link></p>
          </div>
        </div>
      </section>
    </div>
  );
}

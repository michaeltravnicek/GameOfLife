import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import FormInput from '../../components/FormInput/FormInput';
import Button from '../../components/Button/Button';
import '../Login/AuthPage.css';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [first, setFirst] = useState('');
  const [username, setUsername] = useState('');
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
        username,
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
      <div className="stage register-bg" />
      <div className="grain" />
      <section className="hero-section">
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
              <FormInput
                id="reg-first" label="Jméno" type="text"
                placeholder="Jan" autoComplete="given-name"
                value={first} onChange={(e) => setFirst(e.target.value)} required
              />
              <FormInput
                id="reg-username" label="Přezdívka" type="text"
                placeholder="honzic" autoComplete="username"
                value={username} onChange={(e) => setUsername(e.target.value)} required
              />
              <FormInput
                id="reg-phone" label="Telefon (9 číslic)" type="tel"
                placeholder="731 005 976" autoComplete="tel"
                value={phone} onChange={(e) => setPhone(e.target.value)} required
              />
              <FormInput
                id="reg-email" label="E-mail" type="email"
                placeholder="jan@example.com" autoComplete="email"
                value={email} onChange={(e) => setEmail(e.target.value)} required
              />
              <FormInput
                id="reg-pw" label="Heslo" type="password"
                placeholder="········" autoComplete="new-password"
                value={pw} onChange={(e) => setPw(e.target.value)} required
              />
              <FormInput
                id="reg-pw2" label="Potvrdit heslo" type="password"
                placeholder="········" autoComplete="new-password"
                value={pw2} onChange={(e) => setPw2(e.target.value)} required
              />
              {error && <div className="auth-error">{error}</div>}
              <Button type="submit" size="lg" busy={busy} className="pts-btn-wrap">
                {busy ? 'Registruji…' : 'Registrovat se →'}
              </Button>
            </form>
            <p className="auth-foot">Už máš účet? <Link to="/prihlasit">Přihlásit se</Link></p>
          </div>
        </div>
      </section>
    </div>
  );
}

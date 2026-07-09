import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import FormInput from '../../components/FormInput/FormInput';
import Button from '../../components/Button/Button';
import PillTabs from '../../components/PillTabs/PillTabs';
import { TicketFrame } from '../../components/DashedBorder/DashedBorder';
import { extractApiError } from '../../services/errors';
import '../Login/AuthPage.css';
import './RegisterVariants.css';

// TEMPORARY — page design exploration (see RegisterVariants.css). Fold the
// winner into AuthPage.css and delete the switcher + variants file.
// ?v=frost|lb|plakat preselects a design for sharing previews.
const REG_VARIANTS = [
  { key: 'frost', label: 'Frost' },
  { key: 'lb', label: 'Leaderboard' },
  { key: 'plakat', label: 'Plakát' },
];

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [first, setFirst] = useState('');
  const [username, setUsername] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [variant, setVariant] = useState(() => {
    const q = new URLSearchParams(window.location.search).get('v');
    return REG_VARIANTS.some((v) => v.key === q) ? q : 'frost';
  });

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
      navigate(location.state?.from || `/profil/${u.username}`, { replace: true });
    } catch (err) {
      setError(extractApiError(err, 'Registrace selhala.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`auth-page reg-v-${variant}`}>
      <div className="stage register-bg" />
      <div className="grain" />

      {/* TEMPORARY — page design switcher (remove after picking a winner) */}
      <section className="reg-variant-row" aria-label="Náhled designu registrace">
        <span className="rv-label">Design stránky</span>
        <PillTabs tabs={REG_VARIANTS} active={variant} onChange={setVariant} />
      </section>

      <section className="hero-section">
        <div className="hero-inner">
          <div className="hero-eyebrow">Game of Life · Sezóna 2025/26</div>
          <h1 className="hero-title">Začni hrát život naplno!</h1>
          <p className="hero-sub">Vytvoř si účet, sbírej body a hraj naplno.</p>
        </div>
      </section>

      <section className="auth-container">
        <div className="auth-card wide">
          {variant === 'plakat' && <TicketFrame />}
          {variant === 'plakat' && <img className="reg-badge" src="/img/GOL_C50_transparent.webp" alt="" width="126" height="126" />}
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
              <Button type="submit" variant="nav" size="lg" busy={busy} className="pts-btn-wrap">
                {busy ? 'Registruji…' : 'Registrovat se →'}
              </Button>
            </form>
            <p className="auth-foot">Už máš účet? <Link to="/prihlasit" state={location.state}>Přihlásit se</Link></p>
          </div>
        </div>
      </section>
    </div>
  );
}

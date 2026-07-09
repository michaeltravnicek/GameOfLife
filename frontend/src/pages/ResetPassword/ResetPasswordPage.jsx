import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { apiPasswordResetConfirm } from '../../services/api';
import { useToast } from '../../components/Toast/ToastProvider';
import FormInput from '../../components/FormInput/FormInput';
import Button from '../../components/Button/Button';
import { TicketFrame } from '../../components/DashedBorder/DashedBorder';
import '../Login/AuthPage.css';

const MIN_LEN = 8;

// Target of the link in accounts/templates/accounts/password_reset_email.html:
//   {protocol}://{domain}/obnova-hesla/{uid}/{token}/
export default function ResetPasswordPage() {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (pw.length < MIN_LEN) {
      setError(`Heslo musí mít alespoň ${MIN_LEN} znaků.`);
      return;
    }
    if (pw !== pw2) {
      setError('Hesla se neshodují.');
      return;
    }
    setBusy(true);
    try {
      await apiPasswordResetConfirm(uid, token, pw);
      toast.success('Heslo bylo změněno. Můžeš se přihlásit.', { title: 'Hotovo' });
      navigate('/prihlasit');
    } catch (err) {
      const msg = err.response?.data?.error
        || 'Odkaz je neplatný nebo vypršel. Požádej o nový.';
      setError(msg);
      toast.error(msg, { title: 'Chyba' });
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
          <h1 className="hero-title">Nové heslo</h1>
          <p className="hero-sub">Zvol si nové heslo a jsi zpátky ve hře.</p>
        </div>
      </section>

      <section className="auth-container">
        <div className="auth-card">
          <TicketFrame />
          <div className="auth-card-inner">
            <div className="auth-card-tag">Game of Life</div>
            <h2 className="auth-card-title">Nastavit nové heslo</h2>
            <div className="auth-card-sub">Zadej nové heslo dvakrát pro kontrolu.</div>
            <div className="auth-divider" />

            <form onSubmit={handleSubmit} noValidate>
              <FormInput
                id="rp-pw"
                label="Nové heslo"
                type="password"
                autoComplete="new-password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                required
              />
              <FormInput
                id="rp-pw2"
                label="Nové heslo znovu"
                type="password"
                autoComplete="new-password"
                value={pw2}
                onChange={(e) => setPw2(e.target.value)}
                required
              />
              {error && <div className="auth-error">{error}</div>}
              <Button type="submit" variant="action" size="lg" busy={busy} className="pts-btn-wrap">
                {busy ? 'Ukládám…' : 'Nastavit heslo →'}
              </Button>
              <p className="auth-foot">
                <Link to="/prihlasit">← Zpět na přihlášení</Link>
              </p>
            </form>
          </div>
        </div>
      </section>
    </div>
  );
}

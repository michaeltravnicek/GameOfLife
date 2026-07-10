import { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPasswordReset } from '../../services/api';
import { useToast } from '../../components/Toast/ToastProvider';
import FormInput from '../../components/FormInput/FormInput';
import Button from '../../components/Button/Button';
import '../Login/AuthPage.css';

export default function ForgotPasswordPage() {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim()) {
      setError('Zadej e-mail.');
      return;
    }
    setBusy(true);
    try {
      const res = await apiPasswordReset(email.trim());
      setSent(true);
      toast.success(res?.message || 'Odkaz pro reset hesla byl odeslán.', {
        title: 'E-mail odeslán',
        duration: 6500,
      });
    } catch (err) {
      const msg = err.response?.data?.error || 'Nepodařilo se odeslat e-mail.';
      setError(msg);
      toast.error(msg, { title: 'Chyba' });
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
            <h2 className="auth-card-title">Reset hesla</h2>
            <div className="auth-card-sub">
              {sent
                ? 'Zkontroluj svou e-mailovou schránku (i složku spam).'
                : 'Zadej e-mail spojený s účtem.'}
            </div>
            <div className="auth-divider" />

            {sent ? (
              <>
                <div className="auth-success">
                  Pokud k <strong>{email}</strong> existuje účet, dorazí ti e-mail s odkazem na obnovení hesla.
                </div>
                <Button as="link" to="/prihlasit" variant="frost" size="lg" busy={busy} className="pts-btn-wrap">
                  ← Zpět na přihlášení
                </Button>
              </>
            ) : (
              <form onSubmit={handleSubmit} noValidate>
                <FormInput
                  id="fp-email"
                  label="E-mail"
                  type="email"
                  placeholder="jan@example.com"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                {error && <div className="auth-error">{error}</div>}
                <Button type="submit" variant="nav" size="lg" busy={busy} className="pts-btn-wrap">
                  {busy ? 'Odesílám…' : 'Poslat odkaz →'}
                </Button>
                <p className="auth-foot">
                  Vzpomněl sis? <Link to="/prihlasit">Přihlásit se</Link>
                </p>
              </form>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

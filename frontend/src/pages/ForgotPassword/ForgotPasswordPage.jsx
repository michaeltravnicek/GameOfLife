import { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPasswordReset } from '../../services/api';
import { extractApiError } from '../../services/errors';
import { toast } from '../../components/Toast/ToastProvider';
import FormInput from '../../components/FormInput/FormInput';
import Button from '../../components/Button/Button';
import AuthShell from '../Login/AuthShell';

export default function ForgotPasswordPage() {
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
      setError(extractApiError(err, 'Nepodařilo se odeslat e-mail.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Reset hesla"
      sub={sent
        ? 'Zkontroluj svou e-mailovou schránku (i složku spam).'
        : 'Zadej e-mail spojený s účtem.'}
    >
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
            {busy ? 'Odesílám…' : <>Poslat odkaz <span className="arr" aria-hidden="true" /></>}
          </Button>
          <p className="auth-foot">
            Vzpomněl sis? <Link to="/prihlasit">Přihlásit se</Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}

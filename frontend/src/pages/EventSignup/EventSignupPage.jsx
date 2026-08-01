import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  fetchEventDetail,
  fetchSignupForm,
  setRsvp,
  submitSignupForm,
} from '../../services/api';
import { useCachedQuery, invalidateQuery } from '../../services/queryCache';
import { reportError } from '../../services/errors';
import { CACHE_TTL } from '../../constants/config';
import { useAuth } from '../../context/AuthContext';
import Button from '../../components/Button/Button';
import { fmtDateShort, fmtTime } from '../../utils/date';
import { toFormUrls } from './embedUrl';
import FormField from './FormFields';
import './EventSignupPage.css';

/**
 * Step two of signing up for an event: the event's Google Form, rendered with
 * the site's own inputs.
 *
 * The backend reads the form's questions off Google's respondent page and
 * posts the answers back, so responses still land in the organiser's usual
 * spreadsheet — but the fields on screen are ours, which an iframe could never
 * be (cross-origin, so our CSS stops at its border).
 *
 * When the form can't be read — Google changing their page format, an exotic
 * question type — the API says `embed_only` and we fall back to the iframe.
 * Google-styled beats absent.
 *
 * The RSVP is already recorded by the time anyone lands here; this page never
 * signs someone up as a side effect of being opened.
 */
export default function EventSignupPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState({});
  const [errors, setErrors] = useState({});
  const [sent, setSent] = useState(false);
  // Which URL has finished loading — not a bare boolean, so swapping events
  // can't inherit the previous frame's "loaded" state.
  const [loadedUrl, setLoadedUrl] = useState(null);

  const { data: event, error: queryError, refetch: refetchEvent } = useCachedQuery(
    `event:${slug}`,
    () => fetchEventDetail(slug),
    { enabled: !!slug, ttl: CACHE_TTL.EVENT_DETAIL },
  );

  // Only fetched once we know the event actually has a form: the endpoint 404s
  // otherwise, and reading it costs Google a page fetch on a cache miss.
  const { data: form, error: formError } = useCachedQuery(
    `signup-form:${slug}`,
    () => fetchSignupForm(slug),
    { enabled: !!slug && !!event?.survey_url, ttl: CACHE_TTL.EVENT_DETAIL },
  );

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/prihlasit', { replace: true, state: { from: `/events/${slug}/prihlaska` } });
    }
  }, [authLoading, user, navigate, slug]);

  // Nothing to show for an event with neither a form nor a group.
  useEffect(() => {
    if (event && !event.survey_url && !event.whatsapp_url) {
      navigate(`/events/${slug}`, { replace: true });
    }
  }, [event, navigate, slug]);

  const formUrls = useMemo(() => toFormUrls(event?.survey_url), [event?.survey_url]);
  const embedUrl = formUrls?.embed ?? null;
  const frameLoaded = !!embedUrl && loadedUrl === embedUrl;
  const fields = form && !form.embed_only ? form.fields : null;

  const setAnswer = (id) => (next) => {
    setAnswers((prev) => ({ ...prev, [id]: next }));
    // Clear the server's complaint as soon as the field is touched; leaving it
    // up while the user fixes it reads as "still wrong".
    setErrors((prev) => (prev[id] ? { ...prev, [id]: undefined } : prev));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {};
    fields.forEach((f) => {
      const v = answers[f.entry_id];
      const filled = Array.isArray(v) ? v.length > 0 : (v ?? '') !== '';
      if (filled) payload[f.entry_id] = v;
    });

    setBusy(true);
    setErrors({});
    try {
      await submitSignupForm(slug, payload);
      setSent(true);
    } catch (err) {
      const fieldErrors = err.response?.status === 400 && err.response.data?.errors;
      if (fieldErrors) {
        setErrors(fieldErrors);
      } else {
        reportError('Odeslání formuláře se nepodařilo. Zkus to prosím znovu.', err);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleDone = () => navigate(`/events/${slug}`);

  const handleCancel = async () => {
    setBusy(true);
    try {
      await setRsvp(slug, false);
      invalidateQuery((k) => k.startsWith('events:'));
      await refetchEvent();
      navigate(`/events/${slug}`);
    } catch (err) {
      reportError('Zrušení účasti se nepodařilo.', err);
    } finally {
      setBusy(false);
    }
  };

  // Deep link or a back-button return can land someone here without an RSVP.
  const handleJoin = async () => {
    setBusy(true);
    try {
      await setRsvp(slug, true);
      invalidateQuery((k) => k.startsWith('events:'));
      await refetchEvent();
    } catch (err) {
      reportError('Přihlášení se nepodařilo. Zkus to prosím znovu.', err);
    } finally {
      setBusy(false);
    }
  };

  if (queryError) {
    return (
      <div className="gol-page event-signup-page">
        <div className="signup-body">
          <main className="signup-main">
            <p className="signup-state">
              {queryError.response?.status === 404 ? 'Akce nenalezena.' : 'Nepodařilo se načíst akci.'}
            </p>
            <div className="signup-actions">
              <Button as="link" to="/events" variant="frost">← Zpět na všechny akce</Button>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="gol-page event-signup-page">
        <div className="signup-body">
          <main className="signup-main"><p className="signup-state">Načítám…</p></main>
        </div>
      </div>
    );
  }

  return (
    <div className="gol-page event-signup-page">

      {/* HEAD — the event, restated, so the form never floats context-free */}
      <header className="signup-hero">
        <div className="signup-hero-inner">
          <div className="u-label signup-eyebrow">— Přihláška —</div>
          <h1 className="signup-title">{event.name}</h1>
          <div className="signup-meta">
            <span className="signup-pts">+{event.points} pts</span>
            <span className="signup-meta-item">{fmtDateShort(event.date)}</span>
            {!event.time_tbd && <span className="signup-meta-item">{fmtTime(event.date)}</span>}
            {event.place && <span className="signup-meta-item">{event.place}</span>}
          </div>
          <p className="signup-lead">
            {event.has_rsvp
              ? <>Místo máš zabrané. Zbývá vyplnit <span className="pink">krátký formulář</span> níž.</>
              : <>Ještě nejsi na akci přihlášen/a — dokonči to tlačítkem níž.</>}
          </p>
        </div>
      </header>

      <div className="signup-body">
        <main className="signup-main">

          {!event.has_rsvp && (
            <div className="signup-notice">
              <p className="signup-notice-text">
                Tvoje přihláška zatím není uložená. Klikni na <strong>Přihlásit se</strong>,
                pak vyplň formulář.
              </p>
              <Button variant="action" onClick={handleJoin} busy={busy} disabled={event.is_full}>
                {event.is_full ? 'Plně obsazeno' : 'Přihlásit se'}
              </Button>
            </div>
          )}

          {event.survey_url && (
            <section className="signup-section">
              <div className="signup-sec-head">
                <span className="u-label">— Formulář —</span>
                <h2 className="signup-sec-title">{form?.title || 'Pár informací navíc'}</h2>
              </div>

              {sent ? (
                <div className="signup-done">
                  <p className="signup-done-text">
                    Odesláno. <span className="pink">Díky!</span> Odpovědi máme, uvidíme se na akci.
                  </p>
                </div>
              ) : formError ? (
                <div className="signup-fallback">
                  <p className="signup-fallback-text">Formulář se nepodařilo načíst.</p>
                  {formUrls && (
                    <Button as="a" href={formUrls.open} variant="nav" target="_blank" rel="noopener noreferrer">
                      Otevřít formulář ↗
                    </Button>
                  )}
                </div>
              ) : !form ? (
                <p className="signup-state">Načítám formulář…</p>
              ) : fields ? (
                /* The whole point: real inputs, our CSS. */
                <form className="gol-card signup-form" onSubmit={handleSubmit} noValidate>
                  {fields.map((f) => (
                    <FormField
                      key={f.entry_id}
                      field={f}
                      value={answers[f.entry_id]}
                      onChange={setAnswer(f.entry_id)}
                      error={errors[f.entry_id]}
                    />
                  ))}
                  <div className="signup-form-foot">
                    <Button type="submit" variant="action" busy={busy}>
                      Odeslat <span className="arr" aria-hidden="true" />
                    </Button>
                    <p className="signup-form-note">Odpovědi jdou do formuláře akce.</p>
                  </div>
                </form>
              ) : embedUrl ? (
                /* Unreadable form — Google-styled iframe beats no form at all. */
                <div className="signup-ticket">
                  <div className="signup-ticket-strip">
                    <span>Formulář akce</span>
                    <span className="signup-ticket-slug">{event.name}</span>
                  </div>
                  <div className="signup-frame-wrap">
                    {!frameLoaded && <div className="signup-frame-loading">Načítám formulář…</div>}
                    <iframe
                      className={`signup-frame${frameLoaded ? ' ready' : ''}`}
                      src={embedUrl}
                      title={`Přihlašovací formulář — ${event.name}`}
                      loading="lazy"
                      onLoad={() => setLoadedUrl(embedUrl)}
                    />
                  </div>
                  <div className="signup-ticket-foot">
                    Vyplň formulář a odešli ho tlačítkem uvnitř.{' '}
                    <a href={formUrls.open} target="_blank" rel="noopener noreferrer">
                      Otevřít v novém okně ↗
                    </a>
                  </div>
                </div>
              ) : (
                /* Not a Google Form at all — CSP would blank the frame. */
                <div className="signup-fallback">
                  <p className="signup-fallback-text">
                    Formulář nejde zobrazit přímo tady. Otevři ho v novém okně a pak se sem vrať.
                  </p>
                  <Button as="a" href={event.survey_url} variant="nav" target="_blank" rel="noopener noreferrer">
                    Otevřít formulář ↗
                  </Button>
                </div>
              )}
            </section>
          )}

          {event.whatsapp_url && (
            <section className="signup-section">
              <div className="signup-sec-head">
                <span className="u-label">— Skupina —</span>
                <h2 className="signup-sec-title">Ať ti nic neuteče</h2>
              </div>
              <div className="signup-wa">
                <p className="signup-wa-text">
                  Všechny informace k akci posíláme do WhatsApp skupiny. Přidej se.
                </p>
                <Button as="a" href={event.whatsapp_url} variant="nav" target="_blank" rel="noopener noreferrer">
                  Přidat se do skupiny ↗
                </Button>
              </div>
            </section>
          )}

          <div className="signup-actions">
            <Button variant="action" onClick={handleDone} disabled={busy}>
              Hotovo <span className="arr" aria-hidden="true" />
            </Button>
            {event.has_rsvp && (
              <Button variant="ghost" onClick={handleCancel} disabled={busy}>
                Zrušit přihlášku
              </Button>
            )}
          </div>

          <p className="signup-foot-note">
            „Hotovo“ tě jen vrátí na akci — přihlášku máš uloženou, ať formulář vyplníš teď nebo později.
          </p>
        </main>
      </div>
    </div>
  );
}

import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  fetchEventAttendees,
  fetchEventDetail,
  fetchEventRsvps,
  fetchLeaderboard,
  removeEventAttendee,
  setEventAttendeePoints,
  setRsvp,
  submitFeedback,
  uploadEventImages,
} from '../../services/api';
import { useCachedQuery, invalidateQuery } from '../../services/queryCache';
import { reportError } from '../../services/errors';
import { CACHE_TTL } from '../../constants/config';
import { useAuth } from '../../context/AuthContext';
import Button from '../../components/Button/Button';
import SectionHeader from '../../components/SectionHeader/SectionHeader';
import EventLocationMap from '../../components/EventLocationMap/EventLocationMap';
import Modal from '../../components/Modal/Modal';
import PillTabs from '../../components/PillTabs/PillTabs';
import TicketList from '../../components/StatList/TicketList';
import { eventList, EVENT_LIST_CLASS } from '../../components/StatList/eventColumns';
import SearchInput from '../../components/SearchInput/SearchInput';
import { fmtDateShort, fmtTime, dayName } from '../../utils/date';
import { isMobileViewport } from '../../utils/img';
import { shareLink } from '../../utils/shareUrl';
import { addEventToCalendar } from '../../utils/calendar';
import { toast } from '../../components/Toast/ToastProvider';
import './EventDetailPage.css';

// Lightbox is only needed once the user clicks on an image — pull it off the
// critical bundle and load it on demand.
const Lightbox = lazy(() => import('../../components/Lightbox/Lightbox'));

// Usernames are sometimes e-mail addresses, and "@michael@seznam.cz" reads as
// a typo. Only handle-style usernames get the @ prefix.
const handle = (username) => (username?.includes('@') ? username : `@${username}`);

/**
 * One attendee's points cell. Owns its own draft so typing in one row never
 * re-renders the whole roster, and a rejected edit rolls that row back on
 * its own without touching its neighbours.
 */
function AttendancePointsInput({ attendee, onSave, busy }) {
  const [value, setValue] = useState(String(attendee.points));

  // The roster reloads after every save; adopt the server's number so a
  // rejected edit doesn't leave a stale draft in the input.
  useEffect(() => { setValue(String(attendee.points)); }, [attendee.points]);

  const commit = () => {
    const points = Number(value);
    if (!Number.isInteger(points) || points < 0) {
      setValue(String(attendee.points));
      toast.error('Body musí být celé číslo, nula nebo víc.');
      return;
    }
    if (points !== attendee.points) onSave(attendee.user_id, points);
  };

  return (
    <>
      <input
        type="number"
        min="0"
        className="att-pts-input"
        value={value}
        disabled={busy}
        aria-label={`Body pro ${attendee.name}`}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); }
          if (e.key === 'Escape') setValue(String(attendee.points));
        }}
      />
      <span className="u">pts</span>
    </>
  );
}

export default function EventDetailPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, canUpload, isAdmin } = useAuth();
  const [busy, setBusy] = useState(false);
  const [lbOpen, setLbOpen] = useState(false);
  const [lbIndex, setLbIndex] = useState(0);
  const [rating, setRating] = useState(0);
  const [fbHover, setFbHover] = useState(0);
  const [comment, setComment] = useState('');
  const [fbBusy, setFbBusy] = useState(false);
  const [fbDone, setFbDone] = useState(false);
  const [fbOpen, setFbOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [surveyOpen, setSurveyOpen] = useState(false);

  // Admin-only "Popis" / "Účast a body" toggle — same page, same URL, just a
  // different body section, exactly like the profile page's season/view tabs.
  const [adminView, setAdminView] = useState('popis');
  const [attendees, setAttendees] = useState([]);
  const [rsvps, setRsvps] = useState([]);
  const [attLoading, setAttLoading] = useState(false);
  const [attLoaded, setAttLoaded] = useState(false);
  const [busyId, setBusyId] = useState(null);
  // One search box, two modes: 'find' narrows the roster already in the table,
  // 'add' searches every leaderboard player so one can be added to it.
  const [attQuery, setAttQuery] = useState('');
  const [attMode, setAttMode] = useState('find');
  const [pool, setPool] = useState(null);          // all leaderboard players, loaded once

  const { data: event, error: queryError, refetch: refetchEvent } = useCachedQuery(
    `event:${slug}`,
    () => fetchEventDetail(slug),
    { enabled: !!slug, ttl: CACHE_TTL.EVENT_DETAIL },
  );

  // Pre-set "done" state if the server already recorded feedback from this user.
  useEffect(() => {
    if (event?.feedback_given) setFbDone(true);
  }, [event?.feedback_given]);

  // Feedback prompt: for a past event a signed-in user hasn't rated yet, pop
  // the rating modal on first landing — the same way the survey modal appears
  // right after an RSVP. We remember the prompt per event so it never nags
  // twice; the "Ohodnotit akci" button reopens it on demand.
  useEffect(() => {
    if (!user || !event?.is_past || event?.feedback_given) return;
    const key = `gol_fb_prompted:${slug}`;
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, '1');
    setFbOpen(true);
  }, [user, event?.is_past, event?.feedback_given, slug]);

  const loadAttendance = async () => {
    setAttLoading(true);
    try {
      const [a, r] = await Promise.all([fetchEventAttendees(slug), fetchEventRsvps(slug)]);
      setAttendees(a.attendees || []);
      setRsvps(r.rsvps || []);
      setAttLoaded(true);
    } catch (err) {
      reportError('Nepodařilo se načíst účast.', err);
    } finally {
      setAttLoading(false);
    }
  };

  // Lazy: only admins ever open this tab, so nobody else pays for the fetch.
  // Loads once when the tab is first opened for this event.
  useEffect(() => {
    if (isAdmin && adminView === 'ucast' && !attLoaded) loadAttendance();
  }, [isAdmin, adminView, attLoaded]);

  // A route-param change (navigating between events) doesn't remount this
  // component, so stale attendance from the last event has to be dropped
  // explicitly.
  useEffect(() => {
    setAttLoaded(false);
    setAttendees([]);
    setRsvps([]);
    setAdminView('popis');
    // Feedback state is per-event; clear it so navigating between events never
    // carries one event's rating (or "done" state) onto the next.
    setFbOpen(false);
    setFbDone(false);
    setRating(0);
    setFbHover(0);
    setComment('');
  }, [slug]);

  const attendingIds = useMemo(() => new Set(attendees.map((a) => a.user_id)), [attendees]);
  // 'find' mode narrows the table in place; 'add' mode leaves it untouched so
  // the roster stays readable while you search for someone to add.
  const shownAttendees = useMemo(() => {
    const q = attQuery.trim().toLowerCase();
    if (attMode !== 'find' || !q) return attendees;
    return attendees.filter((a) => a.name.toLowerCase().includes(q));
  }, [attendees, attQuery, attMode]);

  // Attendance can only be given to an existing leaderboard user, so the whole
  // board is the pool the add-picker searches.
  const attMatches = useMemo(() => {
    const q = attQuery.trim().toLowerCase();
    if (attMode !== 'add' || !q || !pool) return [];
    return pool
      .filter((p) => !attendingIds.has(p.id) && p.name.toLowerCase().includes(q))
      .slice(0, 6);
  }, [attQuery, attMode, pool, attendingIds]);

  const error = queryError
    ? (queryError.response?.status === 404 ? 'Akce nenalezena.' : 'Nepodařilo se načíst akci.')
    : '';

  // Gallery shows ImageToEvent entries + community photos only.
  // The main `event.image` is used as the top poster, not in the gallery,
  // so we don't include it here (it would duplicate one of the poster image).
  const images = useMemo(() => {
    if (!event) return [];
    const list = [...(event.official_images || [])];
    (event.user_photos || []).forEach((p) => list.push(p.url));
    return list;
  }, [event]);

  // Top poster: prefer the event's own DB image, then an official photo, then a
  // built-in default. The default is a static asset, so it always resolves even
  // if media serving is down.
  const POSTER_FALLBACK = '/img/gal0.webp';
  const posterSrc = useMemo(() => {
    if (!event) return POSTER_FALLBACK;
    if (event.image) {
      return isMobileViewport() && event.image_mobile ? event.image_mobile : event.image;
    }
    if (event.official_images?.length) return event.official_images[0];
    return POSTER_FALLBACK;
  }, [event]);


  if (error) {
    return (
      <div className="event-detail-page">
        <main className="detail-main">
          <p style={{ textAlign: 'center', padding: '60px 20px' }}>{error}</p>
          <div style={{ textAlign: 'center' }}>
            <Button as="link" to="/events" variant="frost">← Zpět na všechny akce</Button>
          </div>
        </main>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="event-detail-page">
        <p style={{ textAlign: 'center', padding: '120px 20px', color: '#fff' }}>Načítám…</p>
      </div>
    );
  }

  const handleRsvp = async () => {
    if (!user) {
      navigate('/prihlasit', { state: { from: location.pathname } });
      return;
    }
    const wasJoined = !!event.has_rsvp;
    setBusy(true);
    try {
      await setRsvp(slug, !wasJoined);
      // RSVP changed: refresh this event's cache + drop any events list pages
      // (rsvp_count on cards there may now be stale).
      invalidateQuery((k) => k.startsWith('events:'));
      await refetchEvent();
      // Just joined and the event has a follow-up form and/or a WhatsApp group?
      // Prompt for whichever exists.
      if (!wasJoined && (event.survey_url || event.whatsapp_url)) setSurveyOpen(true);
    } catch (err) {
      reportError('RSVP se nepodařilo. Zkus to prosím znovu.', err);
    } finally {
      setBusy(false);
    }
  };

  // Survey modal: "Hotovo" keeps the RSVP, "Zrušit" cancels it.
  const handleSurveyDone = () => setSurveyOpen(false);
  const handleSurveyCancel = async () => {
    setSurveyOpen(false);
    setBusy(true);
    try {
      await setRsvp(slug, false);
      invalidateQuery((k) => k.startsWith('events:'));
      await refetchEvent();
    } catch (err) {
      reportError('Zrušení účasti se nepodařilo.', err);
    } finally {
      setBusy(false);
    }
  };

  const handleFeedback = async (e) => {
    e.preventDefault();
    if (!rating) return;
    setFbBusy(true);
    try {
      await submitFeedback(slug, rating, comment.trim());
      setFbDone(true);
      setFbOpen(false);
      toast.success('Díky za hodnocení!');
    } catch (err) {
      reportError('Nepodařilo se odeslat hodnocení.', err);
    } finally {
      setFbBusy(false);
    }
  };

  // The rating form lives in a modal now; these just open/close it. Opening
  // works for both a first rating and an edit — the current rating/comment stay
  // in state, so re-opening after a submit shows what was sent.
  const openFeedback = () => setFbOpen(true);
  const closeFeedback = () => setFbOpen(false);

  const handleUpload = async (e) => {
    const files = e.target.files;
    if (!files || !files.length) return;
    setUploading(true);
    try {
      await uploadEventImages(slug, files);
      invalidateQuery(`event:${slug}`);
      await refetchEvent();
    } catch (err) {
      reportError('Nahrání obrázků se nepodařilo.', err);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const totalAttendancePoints = attendees.reduce((sum, a) => sum + a.points, 0);

  // Every attendance write moves the leaderboard and this event's own
  // attendee_count. refetchEvent() updates the rsvp bar in place; deliberately
  // NOT invalidateQuery(`event:${slug}`) — that blanks the cached value and
  // would unmount this whole page mid-edit.
  const afterAttendanceChange = async () => {
    invalidateQuery((k) => k.startsWith('leaderboard:'));
    invalidateQuery((k) => k.startsWith('events:'));
    await Promise.all([loadAttendance(), refetchEvent()]);
  };

  const saveAttendancePoints = async (userId, points) => {
    setBusyId(userId);
    try {
      await setEventAttendeePoints(slug, userId, points);
      await afterAttendanceChange();
    } catch (err) {
      reportError('Body se nepodařilo uložit.', err);
    } finally {
      setBusyId(null);
    }
  };

  const removeAttendee = async (attendee) => {
    if (!window.confirm(`Odebrat ${attendee.name} z účasti? Přijde o body za tuto akci.`)) return;
    setBusyId(attendee.user_id);
    try {
      await removeEventAttendee(slug, attendee.user_id);
      await afterAttendanceChange();
      toast.success(`${attendee.name} odebrán/a z účasti.`);
    } catch (err) {
      reportError('Odebrání se nepodařilo.', err);
    } finally {
      setBusyId(null);
    }
  };

  const ensurePlayerPool = async () => {
    if (pool) return;
    try {
      const data = await fetchLeaderboard('all');
      setPool(data.entries || []);
    } catch (err) {
      reportError('Nepodařilo se načíst seznam hráčů.', err);
      setPool([]);
    }
  };

  const addAttendee = async (player) => {
    setBusyId(player.id);
    try {
      await setEventAttendeePoints(slug, player.id, event.points);
      setAttQuery('');
      await afterAttendanceChange();
      toast.success(`${player.name} započítán/a s ${event.points} pts.`);
    } catch (err) {
      reportError('Přidání se nepodařilo.', err);
    } finally {
      setBusyId(null);
    }
  };

  const openLb = (i) => { setLbIndex(i); setLbOpen(true); };
  const rules = event.rules ? event.rules.split(/\n+/).filter(Boolean) : [];
  const displayImages = images.slice(0, 4);
  const imgCount = Math.min(displayImages.length, 4);

  return (
    <div className="event-detail-page">

      {/* POSTER */}
      <section className="poster">
        <img
          className="poster-img"
          src={posterSrc}
          alt={event.name}
          fetchPriority="high"
          onError={(e) => {
            // If the chosen image fails to load (e.g. a missing upload), fall
            // back to the default so the poster never shows a broken image.
            if (e.currentTarget.src !== window.location.origin + POSTER_FALLBACK) {
              e.currentTarget.src = POSTER_FALLBACK;
            }
          }}
        />
        <div className="poster-grain" />
        <div className="poster-vignette" />
        <div className="poster-top">
          <div className="badges">
            <span className={`ev-pill${!event.is_past ? ' live' : ''}`}>
              {event.is_past ? 'Proběhlo' : 'Nadcházející'}
            </span>
          </div>
          {event.logo
            ? <img className="poster-logo" src={event.logo} alt={event.name} style={{ transform: `scale(${event.logo_scale ?? 1})` }} />
            : <img className="poster-logo" src="/img/GOL_main_logo_pink.webp" alt={event.name} />}
        </div>
        <div className="credits">
          <span className="credits-rule" />
          <div className="credit">
            <div className="credit-label">— Datum —</div>
            <div className="credit-value">{fmtDateShort(event.date)}</div>
            <div className="credit-sub">{dayName(event.date)}</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Čas —</div>
            <div className={`credit-value${event.time_tbd ? ' long' : ''}`}>
              {event.time_tbd ? 'Upřesníme' : fmtTime(event.date)}
            </div>
            <div className="credit-sub">{event.name}</div>
          </div>
          <div className="credit">
            <div className="credit-label">— Místo —</div>
            <div className={`credit-value${(event.place || '').length > 12 ? ' xlong' : (event.place || '').length > 8 ? ' long' : ''}`}>{event.place}</div>
            <div className="credit-sub">&nbsp;</div>
          </div>
        </div>
      </section>

      {/* RSVP BAR */}
      <div className="rsvp-bar">
        <div className="rsvp-inner">
          {!event.is_past ? (
            <>
              <div className="rsvp-info">
                <span className="pts-tag">+{event.points} pts</span>
                {event.capacity != null && (
                  <span className="cap-tag">{event.rsvp_count} / {event.capacity} přihlášených</span>
                )}
                {/* Check-in runs during the event, so attendance climbs while
                    the event is still "upcoming". Show it only once someone is
                    actually counted — a standing "0 dorazilo" reads as failure. */}
                {event.attendee_count > 0 && (
                  <span className="cap-tag">{event.attendee_count} dorazilo</span>
                )}
              </div>
              <div className="rsvp-actions">
                {/* Same page, same URL — only the body section below swaps.
                    Lives right beside the RSVP button, not a separate bar. */}
                {isAdmin && (
                  <PillTabs
                    className="admin-view-tabs"
                    tabs={[
                      { key: 'popis', label: 'Popis' },
                      { key: 'ucast', label: 'Účast', badge: attLoaded ? attendees.length : undefined },
                    ]}
                    active={adminView}
                    onChange={setAdminView}
                  />
                )}
                <Button
                  variant="action"
                  className={event.has_rsvp ? 'joined' : ''}
                  onClick={handleRsvp}
                  disabled={event.is_full && !event.has_rsvp}
                  busy={busy}
                >
                  {event.has_rsvp ? '✓ Jsi přihlášen/a' : event.is_full ? 'Plně obsazeno' : 'Přihlásit se ➤'}
                </Button>
              </div>
            </>
          ) : (
            <>
              {/* Sibling of the tabs (not their parent) so the bar's
                  space-between puts them side by side, like the profile
                  page's action bar. */}
              <div className={`rsvp-recap${isAdmin ? ' with-tabs' : ''}`}>
                <span className="recap-eyebrow">— Proběhlo —</span>
                {/* Real attendance, not sign-ups: after the event only the people
                    who were actually counted (and scored) are worth reporting. */}
                <span className="recap-text">{event.attendee_count ?? 0} dorazilo · +{event.points} pts</span>
              </div>
              {isAdmin && (
                <PillTabs
                  className="admin-view-tabs"
                  tabs={[
                    { key: 'popis', label: 'Popis' },
                    { key: 'ucast', label: 'Účast a body', badge: attLoaded ? attendees.length : undefined },
                  ]}
                  active={adminView}
                  onChange={setAdminView}
                />
              )}
            </>
          )}
        </div>
      </div>

      {/* BODY */}
      <div className="body-wrap">
        <main className="detail-main">
          {(!isAdmin || adminView === 'popis') && (
          <>
          {event.description && (
            <section className="section">
              <SectionHeader eyebrow="— Popis —" heading={event.name} />
              <p className="desc-text">{event.description}</p>
            </section>
          )}

          {event.latitude != null && event.longitude != null && (
            <section className="section">
              <SectionHeader eyebrow="— Místo —" heading="Kde nás najdeš" />
              <EventLocationMap
                latitude={event.latitude}
                longitude={event.longitude}
                popupLabel={event.place}
              />
            </section>
          )}

          {rules.length > 0 && (
            <section className="section">
              <SectionHeader eyebrow="— Pravidla —" heading="Hrajme férově" />
              <ol className="rules">
                {rules.map((r, i) => (
                  <li key={i}><span>{r}</span></li>
                ))}
              </ol>
            </section>
          )}

          {(displayImages.length > 0 || canUpload) && (
            <section className="section">
              <SectionHeader eyebrow="— Galerie —" heading="Z této akce" />
              {displayImages.length > 0 && (
                <div className="collage" data-count={imgCount}>
                  {displayImages.map((src, i) => (
                    <figure key={i} onClick={() => openLb(i)}>
                      <img src={src} alt={`Galerie ${i + 1}`} loading="lazy" />
                    </figure>
                  ))}
                </div>
              )}
              {canUpload && (
                <div className="admin-upload">
                  <label className="admin-upload-btn">
                    {uploading ? 'Nahrávám…' : '+ Nahrát fotky k akci'}
                    <input type="file" accept="image/*" multiple hidden disabled={uploading} onChange={handleUpload} />
                  </label>
                </div>
              )}
            </section>
          )}

          {event.is_past && (
            <section className="section fb-section">
              <SectionHeader eyebrow="— Zpětná vazba —" heading="Jak se ti akce líbila?" />
              {isAdmin && (
                <div className="admin-btns">
                  <Link to={`/sprava/zpetna-vazba?event=${slug}`} className="admin-btn fb-admin-link">
                    Zobrazit zpětnou vazbu k akci
                  </Link>
                </div>
              )}
              {!user ? (
                <p className="fb-gate">
                  <Link to="/prihlasit" state={{ from: location.pathname }} className="fb-gate-link">Přihlaš se</Link> a ohodnoť akci.
                </p>
              ) : fbDone ? (
                <div className="fb-done">
                  <p className="fb-thanks">Díky za hodnocení!</p>
                  <button type="button" className="fb-edit-btn" onClick={openFeedback}>
                    Upravit hodnocení
                  </button>
                </div>
              ) : (
                <div className="fb-cta">
                  <p className="fb-gate">Dej vědět, jaké to bylo.</p>
                  <Button variant="action" onClick={openFeedback}>★ Ohodnotit akci</Button>
                </div>
              )}
            </section>
          )}
          </>
          )}

          {/* Attendance is only meaningful once the event has happened; before
              that the only real list is who signed up. Showing both would put
              an empty table on every page. */}
          {isAdmin && adminView === 'ucast' && event.is_past && (
            <>
              <section className="section">
                <SectionHeader
                  eyebrow={`— Účast — ${attendees.length} hráčů `}
                  heading="Kdo dorazil."
                />

                {/* One name box, switched between the two things you can do
                    with a name here: find someone already counted, or add
                    someone who isn't. The typed name carries across the switch,
                    so "not in the list → add them" is one tap. */}
                <div className="att-add">
                  <div className="att-search-row">
                    <SearchInput
                      className="att-search-input"
                      value={attQuery}
                      onChange={(e) => setAttQuery(e.target.value)}
                      placeholder={attMode === 'add'
                        ? 'Jméno hráče, kterého chceš přidat…'
                        : `Najít mezi ${attendees.length} účastníky…`}
                    />
                    <PillTabs
                      className="att-mode-tabs"
                      tabs={[
                        { key: 'find', label: 'Najít' },
                        { key: 'add', label: 'Přidat' },
                      ]}
                      active={attMode}
                      onChange={(key) => {
                        setAttMode(key);
                        // The whole board is only needed once you switch to adding.
                        if (key === 'add') ensurePlayerPool();
                      }}
                    />
                  </div>

                  {attMode === 'add' && attQuery.trim() && (
                    <div className="att-results">
                      {attMatches.length === 0 ? (
                        <p className="att-note">
                          {pool ? 'Nikdo takový. Hráč už musí být v žebříčku.' : 'Hledám…'}
                        </p>
                      ) : attMatches.map((p) => (
                        <button
                          type="button"
                          key={p.id}
                          className="att-result"
                          disabled={busyId === p.id}
                          onClick={() => addAttendee(p)}
                        >
                          <span>{p.name}</span>
                          <span className="att-result-add">+{event.points} pts</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {attLoading && !attLoaded ? (
                  <p className="att-note">Načítám účast…</p>
                ) : (
                  <TicketList
                    // Same ticket list as the profile page's "Akce" table —
                    // rank / name / points, with the name and points cells
                    // rendering a player instead of an event, plus a remove
                    // action appended.
                    {...eventList({
                      include: ['rk', 'info', 'pts'],
                      width: { pts: '130px' },
                      render: {
                        info: (a) => (
                          <>
                            <div className="nm">
                              {/* A linked account gets its public profile;
                                  everyone else has a leaderboard player page. */}
                              <Link
                                className="att-name-link"
                                to={a.profile_username ? `/profil/${a.profile_username}` : `/hrac/${a.user_id}`}
                              >{a.name}</Link>
                            </div>
                            <div className="loc">
                              {a.profile_username ? handle(a.profile_username) : 'bez propojeného účtu'}
                            </div>
                          </>
                        ),
                        pts: (a) => (
                          <AttendancePointsInput
                            attendee={a}
                            onSave={saveAttendancePoints}
                            busy={busyId === a.user_id}
                          />
                        ),
                      },
                      extra: [{
                        key: 'act',
                        className: 'att-act',
                        width: '92px',
                        render: (a) => (
                          <button
                            type="button"
                            className="att-remove"
                            disabled={busyId === a.user_id}
                            aria-label={`Odebrat ${a.name} z účasti`}
                            onClick={() => removeAttendee(a)}
                          >Odebrat</button>
                        ),
                      }],
                    })}
                    // after the spread: keeps ev-grid, adds the hook the
                    // mobile column rules below target
                    className={`${EVENT_LIST_CLASS} att-grid`}
                    rows={shownAttendees}
                    rowKey={(a) => a.user_id}
                    emptyText={attMode === 'find' && attQuery.trim()
                      ? 'Nikdo takový mezi účastníky. Přepni na Přidat a započítej ho.'
                      : 'Zatím nikdo. Přidej hráče výš.'}
                  />
                )}
              </section>
            </>
          )}

          {isAdmin && adminView === 'ucast' && !event.is_past && (
            <section className="section">
              <SectionHeader
                eyebrow={`— Přihlášení — ${rsvps.length}`}
                heading="Kdo se hlásil."
              />
              {attLoading && !attLoaded ? (
                <p className="att-note">Načítám přihlášené…</p>
              ) : (
                <TicketList
                  // Rank / name / signed-up date — the same ticket list, with
                  // the date column showing when they signed up.
                  {...eventList({
                    include: ['rk', 'info', 'dt'],
                    width: { dt: '130px' },
                    render: {
                      info: (r) => (
                        <>
                          <div className="nm">
                            <Link className="att-name-link" to={`/profil/${r.username}`}>
                              {r.name || r.username}
                            </Link>
                          </div>
                          <div className="loc">{handle(r.username)}</div>
                        </>
                      ),
                      dt: (r) => fmtDateShort(r.created_at),
                    },
                  })}
                  className={`${EVENT_LIST_CLASS} rsvp-grid`}
                  rows={rsvps}
                  rowKey={(r) => r.auth_user_id}
                  emptyText="Nikdo se nepřihlásil."
                />
              )}
            </section>
          )}
        </main>
      </div>

      {/* BACK STRIP */}
      <div className="back-strip">
        <div className="back-strip-inner">
          {/* Navigation = 3D buttons (frost for "back"); round pills = in-place actions. */}
          <Button as="link" to="/events" variant="frost">← Zpět na všechny akce</Button>
          <div className="back-strip-actions">
            {isAdmin && (
              <Button as="link" to={`/events/${slug}/upravit`}>
                ✏️ Upravit akci
              </Button>
            )}
            {!event.is_past && (
              <Button
                variant="ghost"
                onClick={async () => {
                  try {
                    await addEventToCalendar(event);
                  } catch {
                    // Cancelled prompt isn't an error; real failures (e.g.
                    // calendar access denied) get one generic toast.
                    toast.error('Akci se nepodařilo přidat do kalendáře.', {
                      title: 'Kalendář',
                    });
                  }
                }}
              >
                📅 Přidat do kalendáře
              </Button>
            )}
            <Button variant="ghost" onClick={() => shareLink(event.name)}>
              Sdílet kámošům
            </Button>
          </div>
        </div>
      </div>

      {lbOpen && (
        <Suspense fallback={null}>
          <Lightbox
            open={lbOpen}
            images={images}
            index={lbIndex}
            onClose={() => setLbOpen(false)}
            onPrev={() => setLbIndex((i) => (i - 1 + images.length) % images.length)}
            onNext={() => setLbIndex((i) => (i + 1) % images.length)}
          />
        </Suspense>
      )}

      <Modal open={surveyOpen && (!!event.survey_url || !!event.whatsapp_url)} labelledBy="survey-modal-title">
        <div className="survey-modal-eyebrow">— Ještě jedna věc —</div>
        <h3 id="survey-modal-title" className="survey-modal-title">
          {event.survey_url
            ? <>Potřebovali bychom od vás <span className="pink">pár informací navíc.</span></>
            : <>Přidej se do <span className="pink">skupiny akce.</span></>}
        </h3>
        <p className="survey-modal-text">
          {event.survey_url ? (
            <>
              Otevřete prosím krátký formulář a vyplňte ho.
              {event.whatsapp_url && ' Přidejte se i do WhatsApp skupiny, ať vám nic neuteče.'}
              {' '}Pak se vraťte sem a klikněte na <strong>Hotovo</strong>.
            </>
          ) : (
            <>Přidejte se do WhatsApp skupiny akce, ať vám neuniknou žádné informace. Pak klikněte na <strong>Hotovo</strong>.</>
          )}
        </p>
        <div className="survey-modal-links">
          {event.survey_url && (
            <a
              className="survey-modal-link"
              href={event.survey_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Otevřít formulář ↗
            </a>
          )}
          {event.whatsapp_url && (
            <a
              className="survey-modal-link"
              href={event.whatsapp_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Přidat se do WhatsApp skupiny ↗
            </a>
          )}
        </div>
        <div className="survey-modal-buttons">
          <Button variant="frost" onClick={handleSurveyCancel} disabled={busy}>Zrušit účast</Button>
          <Button variant="action" onClick={handleSurveyDone} disabled={busy}>Hotovo</Button>
        </div>
      </Modal>

      {/* Feedback pop-up — the same modal shell as the survey prompt. Opens
          automatically for attendees who haven't rated yet, or on demand from
          the "Ohodnotit akci" / "Upravit hodnocení" buttons. */}
      <Modal open={fbOpen} onClose={closeFeedback} labelledBy="fb-modal-title">
        <div className="survey-modal-eyebrow">— Zpětná vazba —</div>
        <h3 id="fb-modal-title" className="survey-modal-title">
          Jak se ti akce <span className="pink">líbila?</span>
        </h3>
        <form className="fb-form" onSubmit={handleFeedback}>
          <div
            className="fb-stars"
            role="radiogroup"
            aria-label="Hodnocení 1 až 10"
            onMouseLeave={() => setFbHover(0)}
          >
            {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
              <button
                type="button"
                key={n}
                // Cumulative fill: every star up to the hovered one (or, with no
                // hover, up to the picked rating) lights up.
                className={`fb-star${n <= (fbHover || rating) ? ' on' : ''}`}
                aria-label={`${n} z 10`}
                aria-pressed={n <= rating}
                onClick={() => setRating(n)}
                onMouseEnter={() => setFbHover(n)}
                onFocus={() => setFbHover(n)}
                onBlur={() => setFbHover(0)}
              >★</button>
            ))}
          </div>
          <div className="fb-scale-hint" aria-hidden="true">
            <span>Nic moc</span>
            <span>Super</span>
          </div>
          <textarea
            className="fb-comment"
            placeholder="Zde je prostor, pokud máte něco na srdíčku…"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
          />
          <div className="fb-actions">
            <Button type="submit" variant="action" busy={fbBusy} disabled={!rating}>
              Odeslat hodnocení
            </Button>
            <button type="button" className="fb-cancel-btn" onClick={closeFeedback}>
              Zavřít
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

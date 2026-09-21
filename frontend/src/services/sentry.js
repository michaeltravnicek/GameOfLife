/**
 * Error reporting. No-op unless VITE_SENTRY_DSN is set, so local dev and CI
 * never send events (and never burn the free-tier quota with our own noise).
 *
 * The DSN is not a secret — it ships inside the JS bundle by design, and is
 * write-only: it can be used to send events, not to read them.
 *
 * Loaded lazily. `@sentry/react` was the largest single dependency in the main
 * chunk — bigger than React itself — and every visitor downloaded and parsed it
 * before the first paint, on the off chance something later broke. Now the SDK
 * is fetched in its own chunk once the page has loaded, and the window before
 * that is covered by two cheap listeners that buffer any early error and replay
 * it into the SDK when it arrives. The one thing lost is the SDK's own
 * breadcrumb trail for the first second or so; the errors themselves are kept.
 */

let sentry = null;          // the loaded module, once init() has run
let loading = null;         // the in-flight import, so init runs once
const buffered = [];        // errors caught before the SDK was ready
const MAX_BUFFERED = 20;    // a render loop must not grow this without bound

function buffer(error, context) {
  if (buffered.length < MAX_BUFFERED) buffered.push([error, context]);
}

// Early listeners — replaced by the SDK's own global handlers once it loads.
const onError = (event) => buffer(event.error ?? event.message);
const onRejection = (event) => buffer(event.reason);

function loadSdk(dsn) {
  if (loading) return loading;
  // Through sentrySdk.js, not the package: see the note there on tree-shaking.
  loading = import('./sentrySdk').then((Sentry) => {
    Sentry.init({
      dsn,
      environment: import.meta.env.MODE,

      // Privacy. The SDK's defaults are tuned for debugging, not for a GDPR
      // footprint, so each category is set explicitly rather than left implicit:
      //
      //   httpBodies — default collects ALL request/response bodies, which here
      //     would mean POST /auth/login/ (password), registration and profile
      //     edits. [] disables body collection entirely.
      //   cookies    — default true. Ours carry the session id and CSRF token.
      //   userInfo   — already defaults to false; pinned so a future SDK default
      //     flip can't silently start attaching identities.
      //
      // Net effect: events carry the stack trace and the URL, no personal data.
      dataCollection: {
        userInfo: false,
        httpBodies: [],
        cookies: false,
        urlQueryParams: false,
      },

      // Errors only. Performance tracing would exhaust the free quota fast and
      // isn't what this is for.
      tracesSampleRate: 0,
    });
    sentry = Sentry;
    window.removeEventListener('error', onError);
    window.removeEventListener('unhandledrejection', onRejection);
    for (const [error, context] of buffered.splice(0)) {
      Sentry.captureException(error, context ? { extra: context } : undefined);
    }
    return Sentry;
  }).catch(() => {
    // The chunk failed to download (ad blocker, flaky network). Nothing to
    // report to, so let the buffer go rather than hold references forever.
    buffered.length = 0;
    window.removeEventListener('error', onError);
    window.removeEventListener('unhandledrejection', onRejection);
    return null;
  });
  return loading;
}

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  window.addEventListener('error', onError);
  window.addEventListener('unhandledrejection', onRejection);

  // After `load`, so the SDK never competes with the first hero image and the
  // page's own API calls for bandwidth. Already loaded (a late init) → now.
  if (document.readyState === 'complete') {
    loadSdk(dsn);
  } else {
    window.addEventListener('load', () => loadSdk(dsn), { once: true });
  }
}

/** Report a caught error (used by ErrorBoundary). Safe when Sentry is off. */
export function reportError(error, context) {
  if (sentry) {
    sentry.captureException(error, context ? { extra: context } : undefined);
  } else if (loading || import.meta.env.VITE_SENTRY_DSN) {
    // SDK on its way (or about to be): hold the error until it lands. With no
    // DSN there is nothing to hold it for — same no-op as before.
    buffer(error, context);
  }
}

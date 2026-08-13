import * as Sentry from '@sentry/react';

/**
 * Error reporting. No-op unless VITE_SENTRY_DSN is set, so local dev and CI
 * never send events (and never burn the free-tier quota with our own noise).
 *
 * The DSN is not a secret — it ships inside the JS bundle by design, and is
 * write-only: it can be used to send events, not to read them.
 */
export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

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
}

/** Report a caught error (used by ErrorBoundary). Safe when Sentry is off. */
export function reportError(error, context) {
  Sentry.captureException(error, context ? { extra: context } : undefined);
}

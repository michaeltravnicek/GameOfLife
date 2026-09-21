import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./sentrySdk', () => ({
  init: vi.fn(),
  captureException: vi.fn(),
}));

import * as Sentry from './sentrySdk';

const DSN = 'https://public@o1.ingest.de.sentry.io/1';

// Flush the dynamic import + the .then() chain inside loadSdk.
const settle = () => new Promise((r) => setTimeout(r, 0));

describe('sentry service (lazy load)', () => {
  beforeEach(() => {
    vi.resetModules();
    Sentry.init.mockClear();
    Sentry.captureException.mockClear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('does nothing without a DSN', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', '');
    const { initSentry, reportError } = await import('./sentry');
    initSentry();
    window.dispatchEvent(new Event('load'));
    await settle();
    reportError(new Error('x'));
    expect(Sentry.init).not.toHaveBeenCalled();
    expect(Sentry.captureException).not.toHaveBeenCalled();
  });

  it('initialises only after the page has loaded, not on the critical path', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', DSN);
    Object.defineProperty(document, 'readyState', { configurable: true, value: 'loading' });
    const { initSentry } = await import('./sentry');
    initSentry();
    await settle();
    expect(Sentry.init).not.toHaveBeenCalled();

    window.dispatchEvent(new Event('load'));
    await settle();
    expect(Sentry.init).toHaveBeenCalledTimes(1);
    const opts = Sentry.init.mock.calls[0][0];
    expect(opts.dsn).toBe(DSN);
    // The GDPR knobs must survive the refactor: no bodies, no cookies, no user.
    expect(opts.dataCollection).toEqual({
      userInfo: false, httpBodies: [], cookies: false, urlQueryParams: false,
    });
    expect(opts.tracesSampleRate).toBe(0);
  });

  it('keeps errors thrown before the SDK arrives and replays them once', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', DSN);
    Object.defineProperty(document, 'readyState', { configurable: true, value: 'loading' });
    const { initSentry, reportError } = await import('./sentry');
    initSentry();

    // 1. A render error caught by ErrorBoundary before the chunk is here.
    const boundaryErr = new Error('render blew up');
    reportError(boundaryErr, { componentStack: 'at App' });
    // 2. An uncaught error and a rejected promise in the same window.
    const uncaught = new Error('uncaught');
    window.dispatchEvent(Object.assign(new Event('error'), { error: uncaught }));
    const rejected = new Error('rejected');
    window.dispatchEvent(Object.assign(new Event('unhandledrejection'), { reason: rejected }));
    expect(Sentry.captureException).not.toHaveBeenCalled();

    const removed = vi.spyOn(window, 'removeEventListener');
    window.dispatchEvent(new Event('load'));
    await settle();
    expect(Sentry.captureException).toHaveBeenCalledTimes(3);
    expect(Sentry.captureException).toHaveBeenCalledWith(boundaryErr, { extra: { componentStack: 'at App' } });
    expect(Sentry.captureException).toHaveBeenCalledWith(uncaught, undefined);
    expect(Sentry.captureException).toHaveBeenCalledWith(rejected, undefined);

    // Once loaded the early listeners are gone: the SDK's own global handlers
    // take over, so a later window error is not double-reported through us.
    // (Asserted via the spy: vitest's jsdom re-throws any dispatched `error`
    // event once no user listener is attached, so dispatching one here would
    // fail the run for the wrong reason.)
    expect(removed).toHaveBeenCalledWith('error', expect.any(Function));
    expect(removed).toHaveBeenCalledWith('unhandledrejection', expect.any(Function));
    removed.mockRestore();

    // reportError now goes straight through.
    Sentry.captureException.mockClear();
    const late = new Error('late');
    reportError(late);
    expect(Sentry.captureException).toHaveBeenCalledWith(late, undefined);
  });

  it('loads immediately when init runs after the load event already fired', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', DSN);
    Object.defineProperty(document, 'readyState', { configurable: true, value: 'complete' });
    const { initSentry } = await import('./sentry');
    initSentry();
    await settle();
    expect(Sentry.init).toHaveBeenCalledTimes(1);
  });
});

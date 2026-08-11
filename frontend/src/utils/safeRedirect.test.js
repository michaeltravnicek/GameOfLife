import { describe, it, expect } from 'vitest';
import { safeRedirect } from './safeRedirect';

const FALLBACK = '/profil/honza';

describe('safeRedirect', () => {
  it('passes through the in-app paths the 401 interceptor actually produces', () => {
    // api.js builds `?from=` as window.location.pathname + search, so these are
    // the real shapes. If any of them were rejected, session-expiry would stop
    // returning people to the page they were on.
    expect(safeRedirect('/leaderboard', FALLBACK)).toBe('/leaderboard');
    expect(safeRedirect('/events/letni-grilovacka', FALLBACK)).toBe('/events/letni-grilovacka');
    expect(safeRedirect('/galerie?season_id=3', FALLBACK)).toBe('/galerie?season_id=3');
    expect(safeRedirect('/', FALLBACK)).toBe('/');
  });

  it('rejects protocol-relative targets', () => {
    // `//evil.com` is a URL, not a path — the browser reads it as "same scheme,
    // different host".
    expect(safeRedirect('//evil.com', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('//evil.com/prihlasit', FALLBACK)).toBe(FALLBACK);
  });

  it('rejects the backslash bypass from GHSA-wrjc-x8rr-h8h6', () => {
    // The advisory this helper exists for: React Router < 7.15.1 read these as
    // ordinary paths, and the browser then normalised `\` to `/`.
    expect(safeRedirect('\\/\\/evil.com', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('\\\\evil.com', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('/\\evil.com', FALLBACK)).toBe(FALLBACK);
  });

  it('rejects absolute URLs of any scheme', () => {
    expect(safeRedirect('https://evil.com', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('http://evil.com', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('javascript:alert(1)', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('data:text/html,<script>', FALLBACK)).toBe(FALLBACK);
  });

  it('rejects anything that is not a non-empty string starting with /', () => {
    // `searchParams.get()` returns null when the param is absent, which is the
    // common case — it has to land on the fallback, not crash.
    expect(safeRedirect(null, FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect(undefined, FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect('leaderboard', FALLBACK)).toBe(FALLBACK);
    expect(safeRedirect({ pathname: '/leaderboard' }, FALLBACK)).toBe(FALLBACK);
  });
});

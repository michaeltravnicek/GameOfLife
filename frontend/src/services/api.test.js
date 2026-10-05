import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import api, { isSessionLoss, onSessionLoss } from './api';

// Drives the response interceptor without a network: the per-request adapter
// rejects the way axios does for an HTTP error.
const failWith = (status, data, url = '/events/x/update/') => api.request({
  url,
  method: 'patch',
  adapter: (config) => Promise.reject(Object.assign(new Error(`HTTP ${status}`), {
    config,
    response: { status, data, headers: {}, config },
  })),
});

const realLocation = window.location;
let assign;
let listener;
let unsubscribe;

const setPath = (pathname) => {
  assign = vi.fn();
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { pathname, search: '?tab=1', assign },
  });
};

beforeEach(() => {
  setPath('/events/x/upravit');
  listener = vi.fn();
  unsubscribe = onSessionLoss(listener);
});

afterEach(() => {
  unsubscribe();
  Object.defineProperty(window, 'location', { configurable: true, value: realLocation });
});

describe('isSessionLoss', () => {
  it('is true for 401 and for a 403 tagged not_authenticated', () => {
    expect(isSessionLoss({ response: { status: 401 } })).toBe(true);
    expect(isSessionLoss({ response: { status: 403, data: { code: 'not_authenticated' } } })).toBe(true);
  });

  it('is false for a plain permission 403 and for network errors', () => {
    expect(isSessionLoss({ response: { status: 403, data: { error: 'Vyžaduje roli administrátora.' } } })).toBe(false);
    expect(isSessionLoss({})).toBe(false);
  });
});

describe('session-loss interceptor', () => {
  it('redirects to login and clears auth on a not_authenticated 403', async () => {
    await expect(failWith(403, { error: 'Nepřihlášen.', code: 'not_authenticated' })).rejects.toThrow();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(assign).toHaveBeenCalledWith(
      `/prihlasit?from=${encodeURIComponent('/events/x/upravit?tab=1')}`,
    );
  });

  it('leaves a genuine permission 403 alone', async () => {
    await expect(failWith(403, { error: 'Vyžaduje roli administrátora.' })).rejects.toThrow();
    expect(listener).not.toHaveBeenCalled();
    expect(assign).not.toHaveBeenCalled();
  });

  it('still redirects on a 401', async () => {
    await expect(failWith(401, { error: 'x' })).rejects.toThrow();
    expect(assign).toHaveBeenCalledTimes(1);
  });

  it('ignores the auth probe endpoints', async () => {
    await expect(failWith(403, { code: 'not_authenticated' }, '/auth/logout/')).rejects.toThrow();
    await expect(failWith(401, {}, '/auth/me/')).rejects.toThrow();
    expect(listener).not.toHaveBeenCalled();
    expect(assign).not.toHaveBeenCalled();
  });

  it('on the login page clears auth but does not redirect', async () => {
    setPath('/prihlasit');
    await expect(failWith(403, { code: 'not_authenticated' })).rejects.toThrow();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(assign).not.toHaveBeenCalled();
  });
});

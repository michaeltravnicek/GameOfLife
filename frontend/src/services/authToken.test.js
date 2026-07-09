import { describe, it, expect, vi, beforeEach } from 'vitest';

// In-memory stand-in for Capacitor Preferences (native key-value storage).
const store = new Map();
vi.mock('@capacitor/preferences', () => ({
  Preferences: {
    get: vi.fn(async ({ key }) => ({ value: store.get(key) ?? null })),
    set: vi.fn(async ({ key, value }) => { store.set(key, value); }),
    remove: vi.fn(async ({ key }) => { store.delete(key); }),
  },
}));

import { getToken, loadToken, persistToken, clearToken } from './authToken';

describe('authToken', () => {
  beforeEach(async () => {
    store.clear();
    await clearToken();
  });

  it('starts with no token', () => {
    expect(getToken()).toBeNull();
  });

  it('persistToken makes the token available synchronously', async () => {
    await persistToken('abc123');
    expect(getToken()).toBe('abc123');
  });

  it('persistToken survives a reload (loadToken restores from storage)', async () => {
    await persistToken('abc123');
    // Simulate app restart: memory is gone, storage remains.
    await clearMemoryOnly();
    expect(getToken()).toBeNull();
    await loadToken();
    expect(getToken()).toBe('abc123');
  });

  it('clearToken removes both memory and storage', async () => {
    await persistToken('abc123');
    await clearToken();
    expect(getToken()).toBeNull();
    await loadToken();
    expect(getToken()).toBeNull();
  });

  it('loadToken returns null when storage is empty', async () => {
    expect(await loadToken()).toBeNull();
  });
});

// Reset only the module's in-memory mirror by round-tripping loadToken
// against a temporarily emptied... — simpler: stash and restore the store.
async function clearMemoryOnly() {
  const saved = new Map(store);
  store.clear();
  await loadToken();          // memory now null (storage empty)
  for (const [k, v] of saved) store.set(k, v);  // storage restored
}

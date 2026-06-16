import { Preferences } from '@capacitor/preferences';

const KEY = 'auth_token';

// Axios request interceptors are synchronous, so the token is mirrored in
// memory; Preferences (native storage, survives app restarts — unlike
// localStorage, which WKWebView may evict) is the source of truth.
let token = null;

export function getToken() {
  return token;
}

// Called once at app boot, before the first render/API call.
export async function loadToken() {
  const { value } = await Preferences.get({ key: KEY });
  token = value || null;
  return token;
}

export async function persistToken(value) {
  token = value;
  await Preferences.set({ key: KEY, value });
}

export async function clearToken() {
  token = null;
  await Preferences.remove({ key: KEY });
}

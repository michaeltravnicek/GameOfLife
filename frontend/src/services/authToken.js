// DORMANT — nothing imports this module.
//
// The Capacitor app it served is cancelled and the backend no longer accepts
// token auth at all (see DEFAULT_AUTHENTICATION_CLASSES in mysite/settings.py),
// so storing a token here would accomplish nothing. Kept only so a future native
// client has a starting point; if one is revived, the credential it stores should
// be short-lived and refreshable, not a permanent DRF token.
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

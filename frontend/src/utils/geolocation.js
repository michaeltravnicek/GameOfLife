import { Geolocation } from '@capacitor/geolocation';
import { isNative } from '../services/platform';

const OPTS = { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 };

// Normalized failure reasons; callers map them to Czech copy.
// 'denied' | 'denied-forever' | 'unavailable' | 'timeout' | 'unsupported'
export class GeoError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

function webPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new GeoError('unsupported'));
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (err) => {
        if (err.code === 1) reject(new GeoError('denied'));
        else if (err.code === 3) reject(new GeoError('timeout'));
        else reject(new GeoError('unavailable'));
      },
      OPTS,
    );
  });
}

async function nativePosition() {
  // The plugin (unlike the webview's navigator.geolocation) drives the OS
  // permission dialog directly and can report a permanent denial, which on
  // mobile is only fixable in system settings.
  let status = await Geolocation.checkPermissions();
  if (status.location === 'prompt' || status.location === 'prompt-with-rationale') {
    status = await Geolocation.requestPermissions();
  }
  if (status.location === 'denied') throw new GeoError('denied-forever');
  try {
    const pos = await Geolocation.getCurrentPosition(OPTS);
    return { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
  } catch (err) {
    const msg = String(err?.message || '').toLowerCase();
    if (msg.includes('denied')) throw new GeoError('denied');
    if (msg.includes('timeout')) throw new GeoError('timeout');
    throw new GeoError('unavailable');
  }
}

// Resolves to {latitude, longitude}; rejects with GeoError.
export function getPosition() {
  return isNative ? nativePosition() : webPosition();
}

export const GEO_ERROR_MESSAGES = {
  unsupported: 'Tvůj prohlížeč nepodporuje geolokaci.',
  denied: 'Přístup k poloze zamítnut — povol ho a zkus to znovu.',
  'denied-forever': 'Přístup k poloze je zakázaný — povol polohu v nastavení telefonu.',
  unavailable: 'Poloha není dostupná.',
  timeout: 'Časový limit vypršel.',
};

const OPTS = { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 };

// Normalized failure reasons; callers map them to Czech copy.
// 'denied' | 'unavailable' | 'timeout' | 'unsupported'
export class GeoError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

// Resolves to {latitude, longitude}; rejects with GeoError.
export function getPosition() {
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

export const GEO_ERROR_MESSAGES = {
  unsupported: 'Tvůj prohlížeč nepodporuje geolokaci.',
  denied: 'Přístup k poloze zamítnut — povol ho a zkus to znovu.',
  unavailable: 'Poloha není dostupná.',
  timeout: 'Časový limit vypršel.',
};

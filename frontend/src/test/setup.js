import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// React Testing Library renders into a fresh container per test; cleanup
// unmounts it. Without this, leftover trees leak across tests.
afterEach(() => {
  cleanup();
});

// jsdom doesn't ship these — stub safe defaults so production code that
// reads them at module load doesn't blow up.
if (typeof window.matchMedia === 'undefined') {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

if (typeof window.IntersectionObserver === 'undefined') {
  window.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() { return []; }
  };
}

// CheckinBanner reads navigator.geolocation. Stub a permission-denied
// implementation by default; individual tests can override per-call.
if (typeof navigator.geolocation === 'undefined') {
  navigator.geolocation = {
    getCurrentPosition: vi.fn((_ok, fail) => fail && fail({ code: 1, message: 'denied' })),
    watchPosition: vi.fn(),
    clearWatch: vi.fn(),
  };
}

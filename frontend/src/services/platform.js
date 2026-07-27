// The Capacitor app is cancelled, so `isNative` is now always false in practice.
// Auth no longer branches on it (session cookies are the only credential); the
// remaining callers are progressive enhancements — share sheet, geolocation,
// calendar — that already fall back to their web implementations.
import { Capacitor } from '@capacitor/core';

// True when running inside the Capacitor shell (iOS/Android app), false on web.
export const isNative = Capacitor.isNativePlatform();

// 'web' | 'ios' | 'android'
export const platform = Capacitor.getPlatform();

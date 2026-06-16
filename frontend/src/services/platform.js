import { Capacitor } from '@capacitor/core';

// True when running inside the Capacitor shell (iOS/Android app), false on web.
export const isNative = Capacitor.isNativePlatform();

// 'web' | 'ios' | 'android'
export const platform = Capacitor.getPlatform();

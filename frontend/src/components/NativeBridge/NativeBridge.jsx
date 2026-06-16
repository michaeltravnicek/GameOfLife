import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { App as CapApp } from '@capacitor/app';
import { Browser } from '@capacitor/browser';
import { SplashScreen } from '@capacitor/splash-screen';
import { StatusBar, Style } from '@capacitor/status-bar';
import { isNative, platform } from '../../services/platform';
import { useAuth } from '../../context/AuthContext';

/**
 * Glue between the Capacitor shell and the SPA. Renders nothing and no-ops
 * entirely on web. Mounted once inside the Router (App.jsx).
 */
export default function NativeBridge() {
  const navigate = useNavigate();
  const location = useLocation();
  const { loading } = useAuth();

  // Status bar: light icons over the app's dark theme.
  useEffect(() => {
    if (!isNative) return;
    StatusBar.setStyle({ style: Style.Dark }).catch(() => {});
  }, []);

  // Keep the native splash up until the initial auth probe settles, so the
  // app opens straight into the correct logged-in/guest UI (no white flash).
  useEffect(() => {
    if (!isNative || loading) return;
    SplashScreen.hide().catch(() => {});
  }, [loading]);

  // Android hardware back: walk SPA history; exit the app from the home page.
  useEffect(() => {
    if (!isNative || platform !== 'android') return;
    const sub = CapApp.addListener('backButton', ({ canGoBack }) => {
      if (location.pathname !== '/' && canGoBack) {
        navigate(-1);
      } else if (location.pathname !== '/') {
        navigate('/', { replace: true });
      } else {
        CapApp.exitApp();
      }
    });
    return () => {
      sub.then((s) => s.remove());
    };
  }, [navigate, location.pathname]);

  // External links must leave the webview: open them in the system browser
  // (in-app browser sheet). Capture phase so it runs before React handlers.
  useEffect(() => {
    if (!isNative) return;
    const onClick = (e) => {
      const anchor = e.target.closest?.('a[href]');
      if (!anchor) return;
      const href = anchor.getAttribute('href') || '';
      if (!/^https?:\/\//i.test(href)) return;
      try {
        if (new URL(href).origin === window.location.origin) return;
      } catch {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      Browser.open({ url: href }).catch(() => {});
    };
    document.addEventListener('click', onClick, true);
    return () => document.removeEventListener('click', onClick, true);
  }, []);

  return null;
}

import { Share } from '@capacitor/share';
import { isNative } from '../services/platform';
import { toast } from '../components/Toast/ToastProvider';

// Public web URL for shareable links. In the native app window.location.origin
// is capacitor://localhost (iOS) / https://localhost (Android) — useless to
// recipients — so mobile builds set VITE_PUBLIC_WEB_URL to the real site.
export function publicUrl(path = '') {
  const base = import.meta.env.VITE_PUBLIC_WEB_URL || window.location.origin;
  return base.replace(/\/$/, '') + path;
}

// Share the current page (as its public web URL) via the platform share sheet.
// Dismissing the sheet is not an error from the user's POV, so it's swallowed
// silently (navigator.share rejects with AbortError, Capacitor Share likewise).
// Desktop browsers without a share sheet copy the link instead — with a toast,
// so the click doesn't feel like it did nothing.
export function shareLink(title) {
  const url = publicUrl(window.location.pathname);
  if (isNative) {
    Share.share({ title, url }).catch(() => {});
  } else if (navigator.share) {
    navigator.share({ title, url }).catch(() => {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(url)
      .then(() => toast.success('Odkaz zkopírován do schránky.', { title: 'Sdílení' }))
      .catch(() => toast.error('Odkaz se nepodařilo zkopírovat.', { title: 'Sdílení' }));
  } else {
    toast.info(url, { title: 'Odkaz na sdílení', duration: 8000 });
  }
}

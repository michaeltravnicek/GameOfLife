import { toast } from '../components/Toast/ToastProvider';

// Public web URL for shareable links.
export function publicUrl(path = '') {
  return window.location.origin.replace(/\/$/, '') + path;
}

// Share the current page via the browser's share sheet. Dismissing the sheet is
// not an error from the user's POV, so navigator.share's AbortError is swallowed
// silently. Desktop browsers without a share sheet copy the link instead — with
// a toast, so the click doesn't feel like it did nothing.
export function shareLink(title) {
  const url = publicUrl(window.location.pathname);
  if (navigator.share) {
    navigator.share({ title, url }).catch(() => {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(url)
      .then(() => toast.success('Odkaz zkopírován do schránky.', { title: 'Sdílení' }))
      .catch(() => toast.error('Odkaz se nepodařilo zkopírovat.', { title: 'Sdílení' }));
  } else {
    toast.info(url, { title: 'Odkaz na sdílení', duration: 8000 });
  }
}

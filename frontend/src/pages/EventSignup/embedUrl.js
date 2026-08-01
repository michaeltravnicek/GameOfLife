/**
 * Turn an event's `survey_url` into the two URLs the sign-up page needs:
 * one to put in the <iframe src>, one for the "open in a new window" link.
 *
 * Admins paste whatever Google's address bar happens to be showing, and in
 * practice that is the **editor** URL — `/forms/d/<id>/edit?usp=forms_home&
 * ouid=…`. That link is useless to a respondent (they get access-denied) and it
 * carries the author's Google account id, so it must never be handed to a
 * visitor verbatim. Rewriting the path to `/viewform` fixes it: Google 301s
 * `/forms/d/<id>/viewform` to the public `/forms/d/e/<responder-id>/viewform`
 * and preserves the query string while doing it, so we don't need to know the
 * responder id ourselves.
 *
 * Returns null when the URL is not a Google Form at all, which is the page's
 * signal to fall back to a plain link-out rather than frame something CSP will
 * blank out anyway (see mysite/settings.py frame-src).
 */
const FORM_HOSTS = ['docs.google.com', 'forms.gle'];

// Author-side junk from the editor URL. `ouid` is the author's Google account
// id — dropping it is a privacy fix, not a tidy-up.
const AUTHOR_PARAMS = ['ouid', 'usp', 'ths', 'edit_requested'];

export function toFormUrls(rawUrl) {
  if (!rawUrl) return null;
  let url;
  try {
    url = new URL(rawUrl.trim());
  } catch {
    return null;
  }
  if (url.protocol !== 'https:') return null;
  if (!FORM_HOSTS.includes(url.hostname)) return null;

  // Short links resolve on Google's side, after which our query string is long
  // gone — nothing to rewrite, so pass them through untouched.
  if (url.hostname === 'forms.gle') {
    const short = url.toString();
    return { embed: short, open: short };
  }

  // Both shapes: /forms/d/<file-id>/… (editor) and /forms/d/e/<responder-id>/…
  const match = url.pathname.match(/^\/forms\/d\/(e\/)?([^/]+)/);
  if (!match) return null;
  const [, responder, id] = match;

  url.pathname = responder ? `/forms/d/e/${id}/viewform` : `/forms/d/${id}/viewform`;
  url.hash = '';                       // '#responses' would open the wrong tab
  AUTHOR_PARAMS.forEach((p) => url.searchParams.delete(p));

  // Any `entry.*` params survive on purpose: that is how a pre-filled link works.
  const open = url.toString();
  // `embedded=true` is what strips Google's own header/footer chrome, leaving
  // the questions and nothing else.
  url.searchParams.set('embedded', 'true');
  return { embed: url.toString(), open };
}

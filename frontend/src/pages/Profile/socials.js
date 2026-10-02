/**
 * The social profiles a player can link, shared by the profile page (links)
 * and the edit form (inputs). `at`: the site addresses people as @handle, so a
 * stored "@" is stripped and shown once.
 */
export const SOCIALS = [
  { key: 'instagram', label: 'Instagram', ico: 'IG', pre: 'instagram.com/', at: true },
  { key: 'strava', label: 'Strava', ico: 'ST', pre: 'strava.com/athletes/' },
  { key: 'spotify', label: 'Spotify', ico: 'SP', pre: 'spotify.com/user/' },
  { key: 'tiktok', label: 'TikTok', ico: 'TT', pre: 'tiktok.com/@', at: true },
];

// Users often save handles with the "@"; without this the page shows "@@".
const stripAt = (value) => (value || '').replace(/^@+/, '');

/**
 * The link to a profile. The handle is free text from the profile form;
 * encoding pins it to one path segment, so "x?next=…" or "../accounts/login"
 * cannot turn the link into whatever page that site resolves them to.
 */
export function socialHref(social, value) {
  const handle = social.at ? stripAt(value) : value;
  return `https://${social.pre}${encodeURIComponent(handle)}`;
}

export function socialLabel(social, value) {
  return social.at ? `@${stripAt(value)}` : value;
}

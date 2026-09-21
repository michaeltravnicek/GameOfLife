import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../services/api', () => ({
  fetchProfile: vi.fn(),
  fetchProfileSeason: vi.fn(),
}));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false, logout: vi.fn() }),
}));

import { fetchProfile, fetchProfileSeason } from '../../services/api';
import ProfilePage from './ProfilePage';
import { clearCache } from '../../services/queryCache';

// The query cache is module-level and keyed by username; without this the
// second test would render the first test's cached profile.
beforeEach(() => clearCache());

const BASE = {
  username: 'honza', first_name: 'Honza', full_name: 'Honza Novák',
  photo: null, bio: '', city: '', since: 'led 2025',
  instagram: '', strava: '', spotify: '', tiktok: '',
  favourite_categories: [], badges: [], is_own_profile: false,
  upcoming_rsvps: [], past_events: [],
  seasons: [{ id: 1, label: '2026', start: '2026-01-01T00:00:00Z', end: '2026-12-31T00:00:00Z', season_pts: 0, rank: null }],
};

const renderProfile = (payload) => {
  fetchProfile.mockResolvedValue(payload);
  fetchProfileSeason.mockResolvedValue(null);
  return render(
    <MemoryRouter initialEntries={['/profil/honza']}>
      <Routes><Route path="/profil/:username" element={<ProfilePage />} /></Routes>
    </MemoryRouter>,
  );
};

const hrefOf = (container, host) => Array.from(container.querySelectorAll('a.social'))
  .map((a) => a.getAttribute('href'))
  .find((h) => h.includes(host));

describe('profile social links', () => {
  it('links a plain handle as one path segment, with the @ stripped', async () => {
    const { findByText, container } = renderProfile({ ...BASE, instagram: '@honza.novak', tiktok: 'honza_n' });
    await findByText('Honza Novák');
    expect(hrefOf(container, 'instagram.com')).toBe('https://instagram.com/honza.novak');
    expect(hrefOf(container, 'tiktok.com')).toBe('https://tiktok.com/@honza_n');
  });

  it('cannot be steered off the profile path by a crafted handle', async () => {
    // A handle is free text from the profile form. Without encoding, these
    // would link to instagram.com/accounts/login/?next=… and strava.com/?ref=…
    const { findByText, container } = renderProfile({
      ...BASE,
      instagram: '../accounts/login/?next=https://evil.example',
      strava: '12345?ref=evil#frag',
      spotify: 'me/../../login',
    });
    await findByText('Honza Novák');
    const ig = hrefOf(container, 'instagram.com');
    expect(ig.startsWith('https://instagram.com/')).toBe(true);
    expect(ig).not.toContain('?');
    expect(ig).not.toContain('/accounts/');
    expect(ig).toBe(`https://instagram.com/${encodeURIComponent('../accounts/login/?next=https://evil.example')}`);

    const st = hrefOf(container, 'strava.com');
    expect(st).toBe(`https://strava.com/athletes/${encodeURIComponent('12345?ref=evil#frag')}`);
    expect(new URL(st).search).toBe('');
    expect(new URL(st).hash).toBe('');

    const sp = hrefOf(container, 'spotify.com');
    expect(new URL(sp).pathname).toBe(`/user/${encodeURIComponent('me/../../login')}`);
  });

  it('still opens in a new tab without leaking the opener', async () => {
    const { findByText, container } = renderProfile({ ...BASE, instagram: 'honza' });
    await findByText('Honza Novák');
    const a = container.querySelector('a.social');
    expect(a).toHaveAttribute('target', '_blank');
    expect(a.getAttribute('rel')).toContain('noopener');
  });
});

import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../services/api', () => ({
  fetchProfile: vi.fn(),
  fetchProfileSeason: vi.fn(),
  fetchPlayer: vi.fn(),
  fetchPlayerSeason: vi.fn(),
}));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false, logout: vi.fn() }),
}));

import { fetchProfile, fetchProfileSeason, fetchPlayer, fetchPlayerSeason } from '../../services/api';
import ProfilePage from './ProfilePage';
import PlayerPage from '../Player/PlayerPage';

const BASE = {
  username: 'skryty', first_name: 'Skrytý', full_name: 'Skrytý Hráč',
  photo: null, bio: '', city: '', since: 'led 2025',
  instagram: '', strava: '', spotify: '', tiktok: '',
  favourite_categories: [], badges: [], is_own_profile: false,
};

const renderProfile = (payload) => {
  fetchProfile.mockResolvedValue(payload);
  fetchProfileSeason.mockResolvedValue(null);
  return render(
    <MemoryRouter initialEntries={['/profil/skryty']}>
      <Routes><Route path="/profil/:username" element={<ProfilePage />} /></Routes>
    </MemoryRouter>,
  );
};

const renderPlayer = (payload) => {
  fetchPlayer.mockResolvedValue(payload);
  fetchPlayerSeason.mockResolvedValue(null);
  return render(
    <MemoryRouter initialEntries={['/hrac/7']}>
      <Routes><Route path="/hrac/:userId" element={<PlayerPage />} /></Routes>
    </MemoryRouter>,
  );
};

describe('profiles with withheld sections', () => {
  it('profile: events hidden', async () => {
    const { findByText } = renderProfile({
      ...BASE, hidden: ['events'], total_points: 40, total_events: 4, rank: 3,
    });
    expect(await findByText('Skrytý Hráč')).toBeInTheDocument();
  });

  it('profile: points hidden', async () => {
    const { findByText } = renderProfile({
      ...BASE, hidden: ['points'],
      upcoming_rsvps: [], past_events: [],
      seasons: [{ id: 1, label: '2026', start: '2026-01-01T00:00:00Z', end: '2026-12-31T00:00:00Z', season_pts: 0, rank: null }],
    });
    expect(await findByText('Skrytý Hráč')).toBeInTheDocument();
  });

  it('profile: both hidden', async () => {
    const { findByText } = renderProfile({ ...BASE, hidden: ['points', 'events'] });
    expect(await findByText('Skrytý Hráč')).toBeInTheDocument();
  });

  // Under hide_pts the API sends events with no `pts` key at all, so the total
  // cannot be re-added from the rows. Nothing on the page may render that
  // absence as NaN or "undefined".
  it('profile: points hidden, events still listed without their values', async () => {
    const { findByText, container } = renderProfile({
      ...BASE, hidden: ['points'],
      upcoming_rsvps: [],
      past_events: [{ slug: 'beh', name: 'Ranní běh', date: '2026-03-01T09:00:00Z', place: 'Praha' }],
      seasons: [{ id: 1, label: '2026', start: '2026-01-01T00:00:00Z', end: '2026-12-31T00:00:00Z' }],
    });
    await findByText('Skrytý Hráč');
    expect(container.textContent).not.toMatch(/NaN|undefined/);
  });

  it('player: events hidden', async () => {
    const { findByText } = renderPlayer({
      id: 7, name: 'Skrytý Hráč', profile_username: null, badges: [],
      hidden: ['events'], total_points: 40, events_count: 4, rank: 3,
    });
    expect(await findByText('Skrytý Hráč')).toBeInTheDocument();
  });

  it('player: both hidden', async () => {
    const { findByText } = renderPlayer({
      id: 7, name: 'Skrytý Hráč', profile_username: null, badges: [], hidden: ['points', 'events'],
    });
    expect(await findByText('Skrytý Hráč')).toBeInTheDocument();
  });
});

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

vi.mock('../../services/api', () => ({
  fetchGallery: vi.fn(),
  fetchEvents: vi.fn(),
  fetchSeasons: vi.fn(),
  uploadGalleryPhoto: vi.fn(),
  setPhotoLike: vi.fn(),
}));

let authUser = { username: 'honza' };
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: authUser, canUpload: false }),
}));

const reportError = vi.fn();
vi.mock('../../services/errors', () => ({ reportError: (...a) => reportError(...a) }));

import { fetchGallery, fetchEvents, fetchSeasons, setPhotoLike } from '../../services/api';
import { clearCache } from '../../services/queryCache';
import GalleryPage from './GalleryPage';

const photo = (over = {}) => ({
  id: 7,
  url: '/media/p.jpg',
  url_mobile: '/media/p.webp',
  event_name: 'Letní grilovačka',
  event_slug: 'letni-grilovacka',
  event_date: '2026-07-04T18:00:00Z',
  is_user_photo: true,
  uploaded_by: 'Petra N.',
  like_count: 2,
  liked_by_me: false,
  ...over,
});

const renderGallery = async (photos) => {
  fetchGallery.mockResolvedValue({ photos, count: photos.length, has_more: false });
  fetchEvents.mockResolvedValue({ events: [] });
  fetchSeasons.mockResolvedValue({ seasons: [] });
  const view = render(<MemoryRouter><GalleryPage /></MemoryRouter>);
  await screen.findAllByRole('button', { name: /líbí se mi|zrušit lajk/i });
  return view;
};

describe('gallery photo likes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // queryCache lives at module scope, so without this each test renders the
    // previous test's photos from cache instead of its own fixture.
    clearCache();
    authUser = { username: 'honza' };
  });

  it('paints the new state before the request resolves, then keeps the server count', async () => {
    // Never resolves during the assertion below, so what we see is purely the
    // optimistic update — the whole reason the heart feels instant.
    let resolve;
    setPhotoLike.mockReturnValue(new Promise((r) => { resolve = r; }));
    await renderGallery([photo()]);

    const btn = screen.getAllByRole('button', { name: 'Líbí se mi' })[0];
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Zrušit lajk' })[0])
        .toHaveAttribute('aria-pressed', 'true');
    });
    expect(screen.getAllByText('3')[0]).toBeInTheDocument();

    // The server is the final word: it says 9, so 9 wins over our guess of 3.
    resolve({ liked: true, count: 9 });
    await waitFor(() => expect(screen.getAllByText('9')[0]).toBeInTheDocument());
  });

  it('rolls back when the request fails', async () => {
    setPhotoLike.mockRejectedValue(new Error('offline'));
    await renderGallery([photo()]);

    await userEvent.click(screen.getAllByRole('button', { name: 'Líbí se mi' })[0]);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Líbí se mi' })[0])
        .toHaveAttribute('aria-pressed', 'false');
    });
    expect(screen.getAllByText('2')[0]).toBeInTheDocument();
    expect(reportError).toHaveBeenCalled();
  });

  it('sends a guest to login instead of firing the request', async () => {
    authUser = null;
    await renderGallery([photo()]);

    await userEvent.click(screen.getAllByRole('button', { name: 'Líbí se mi' })[0]);

    expect(setPhotoLike).not.toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith('/prihlasit?from=%2Fgalerie');
  });

  it('shows no like button on official event photos', async () => {
    // They arrive with id: null — PhotoLike hangs off UserPhoto only.
    fetchGallery.mockResolvedValue({
      photos: [photo({ id: null, is_user_photo: false, like_count: null })],
      count: 1,
      has_more: false,
    });
    fetchEvents.mockResolvedValue({ events: [] });
    fetchSeasons.mockResolvedValue({ seasons: [] });
    render(<MemoryRouter><GalleryPage /></MemoryRouter>);

    await screen.findByText('Letní grilovačka');
    expect(screen.queryByRole('button', { name: /líbí se mi|zrušit lajk/i })).toBeNull();
  });
});

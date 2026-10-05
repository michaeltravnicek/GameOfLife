import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../../services/api', () => ({
  fetchEventDetail: vi.fn(),
  fetchCategories: vi.fn(),
  fetchBadges: vi.fn(),
  createEvent: vi.fn(),
  updateEvent: vi.fn(),
  deleteEvent: vi.fn(),
}));

let auth;
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../components/Toast/ToastProvider', () => ({ useToast: () => ({}) }));
vi.mock('../../services/errors', () => ({ reportError: vi.fn(), extractApiError: vi.fn() }));
// The form body (map, pickers) is not what these tests are about.
vi.mock('./EventFormSections', () => ({ default: () => <div>Formulář akce</div> }));

import { fetchBadges, fetchCategories, fetchEventDetail } from '../../services/api';
import CreateEventPage from './CreateEventPage';
import EditEventPage from './EditEventPage';

const ADMIN = { user: { username: 'adm' }, loading: false, isAdmin: true };

const renderAt = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/" element={<div>Domů</div>} />
      <Route path="/events/vytvorit" element={<CreateEventPage />} />
      <Route path="/events/:slug/upravit" element={<EditEventPage />} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  fetchCategories.mockResolvedValue({ categories: [] });
  fetchBadges.mockResolvedValue({ badges: [] });
});

describe.each([
  ['create', '/events/vytvorit'],
  ['edit', '/events/akce/upravit'],
])('%s event page guard', (_label, path) => {
  it('waits for auth without fetching', () => {
    auth = { user: null, loading: true, isAdmin: false };
    renderAt(path);
    expect(screen.queryByText('Domů')).not.toBeInTheDocument();
    expect(fetchCategories).not.toHaveBeenCalled();
  });

  it('sends a guest home without fetching', () => {
    auth = { user: null, loading: false, isAdmin: false };
    renderAt(path);
    expect(screen.getByText('Domů')).toBeInTheDocument();
    expect(fetchCategories).not.toHaveBeenCalled();
    expect(fetchEventDetail).not.toHaveBeenCalled();
  });

  it('sends a signed-in non-admin home', () => {
    auth = { user: { username: 'hrac' }, loading: false, isAdmin: false };
    renderAt(path);
    expect(screen.getByText('Domů')).toBeInTheDocument();
    expect(fetchCategories).not.toHaveBeenCalled();
  });
});

describe('edit event page load', () => {
  it('shows an error with a retry instead of an empty form', async () => {
    auth = ADMIN;
    fetchEventDetail.mockRejectedValueOnce(new Error('offline'));
    fetchEventDetail.mockResolvedValueOnce({ name: 'Akce', slug: 'akce' });
    renderAt('/events/akce/upravit');

    expect(await screen.findByText('Akci se nepodařilo načíst. Zkus to znovu.')).toBeInTheDocument();
    expect(screen.queryByText('Formulář akce')).not.toBeInTheDocument();
    expect(screen.queryByText('Vše uloženo')).not.toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Zkusit znovu' }));
    expect(await screen.findByText('Formulář akce')).toBeInTheDocument();
    expect(fetchEventDetail).toHaveBeenCalledTimes(2);
  });
});

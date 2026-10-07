import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

vi.mock('../../services/api', () => ({
  fetchMe: vi.fn(),
  fetchProfile: vi.fn(),
  fetchCategories: vi.fn(),
  fetchProfileQuestions: vi.fn(),
  updateProfile: vi.fn(),
  apiDeleteAccount: vi.fn(),
  apiPasswordChange: vi.fn(),
}));

let auth;
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../components/Toast/ToastProvider', () => ({ toast: {} }));

import { fetchCategories, fetchMe } from '../../services/api';
import EditProfilePage from './EditProfilePage';

function LoginProbe() {
  const location = useLocation();
  return <div>Přihlášení {location.search}</div>;
}

const renderPage = () => render(
  <MemoryRouter initialEntries={['/upravit-profil']}>
    <Routes>
      <Route path="/prihlasit" element={<LoginProbe />} />
      <Route path="/upravit-profil" element={<EditProfilePage />} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => vi.clearAllMocks());

describe('edit profile guard', () => {
  it('waits for auth without fetching', () => {
    auth = { user: null, loading: true };
    renderPage();
    expect(screen.getByText('Načítání profilu…')).toBeInTheDocument();
    expect(fetchMe).not.toHaveBeenCalled();
  });

  it('sends a guest to login with a way back', () => {
    auth = { user: null, loading: false };
    renderPage();
    expect(screen.getByText(`Přihlášení ?from=${encodeURIComponent('/upravit-profil')}`)).toBeInTheDocument();
    expect(fetchMe).not.toHaveBeenCalled();
    expect(fetchCategories).not.toHaveBeenCalled();
  });

  it('loads the profile for a signed-in user', () => {
    auth = { user: { username: 'honza' }, loading: false, refresh: vi.fn() };
    fetchMe.mockReturnValue(new Promise(() => {}));
    fetchCategories.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(fetchMe).toHaveBeenCalledTimes(1);
  });
});

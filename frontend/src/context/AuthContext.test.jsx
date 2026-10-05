import { describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';

let sessionLossListener = null;
vi.mock('../services/api', () => ({
  fetchMe: vi.fn(() => Promise.resolve({ user: { username: 'honza', role: 'admin' } })),
  apiLogin: vi.fn(),
  apiLogout: vi.fn(),
  apiRegister: vi.fn(),
  onSessionLoss: (listener) => {
    sessionLossListener = listener;
    return () => { sessionLossListener = null; };
  },
}));
const clearCache = vi.fn();
vi.mock('../services/queryCache', () => ({ clearCache: () => clearCache() }));

import { AuthProvider, useAuth } from './AuthContext';

function Who() {
  const { user, isAdmin } = useAuth();
  return <div>{user ? `přihlášen ${user.username}${isAdmin ? ' admin' : ''}` : 'host'}</div>;
}

describe('AuthProvider on session loss', () => {
  it('drops the signed-in user and the cached responses', async () => {
    render(<AuthProvider><Who /></AuthProvider>);
    expect(await screen.findByText('přihlášen honza admin')).toBeInTheDocument();

    act(() => sessionLossListener());

    expect(screen.getByText('host')).toBeInTheDocument();
    expect(clearCache).toHaveBeenCalled();
  });
});

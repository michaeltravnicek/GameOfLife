import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { apiLogin, apiLogout, apiRegister, fetchMe } from '../services/api';
import { clearCache } from '../services/queryCache';
import { toast } from '../components/Toast/ToastProvider';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMe();
      setUser(data.user || null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (identifier, password, remember = false) => {
    const data = await apiLogin(identifier, password, remember);
    // New user identity: drop all cached responses that may have been
    // computed against the anonymous user (RSVPs, profile-specific data).
    clearCache();
    setUser(data.user);
    const name = data.user?.first_name || data.user?.full_name || data.user?.username || 'hráči';
    toast.success(`Ahoj, ${name}! Můžeš pokračovat ve hře.`, { title: 'Přihlášení proběhlo' });
    return data.user;
  }, []);

  const register = useCallback(async (payload) => {
    const data = await apiRegister(payload);
    clearCache();
    setUser(data.user);
    const name = data.user?.first_name || data.user?.full_name || data.user?.username || 'nováčku';
    toast.success(`Vítej v Game of Life, ${name}! Hra začíná.`, {
      title: 'Účet vytvořen',
      duration: 6000,
    });
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // ignore
    }
    clearCache();
    setUser(null);
    toast.info('Byl jsi odhlášen. Brzy nashle!', { title: 'Odhlášení' });
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

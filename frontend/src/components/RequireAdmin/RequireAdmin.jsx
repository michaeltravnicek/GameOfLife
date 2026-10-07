import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

// Renders `children` for admins only. The guard runs before the children mount,
// so a visitor without the role never fires their fetches or sees fields they
// cannot save. `fallback` shows while the session is still loading.
export default function RequireAdmin({ fallback = null, children }) {
  const { user, loading, isAdmin } = useAuth();
  if (loading) return fallback;
  if (!user || !isAdmin) return <Navigate to="/" replace />;
  return children;
}

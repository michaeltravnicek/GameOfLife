import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import { ToastProvider, ToastBridge } from './components/Toast/ToastProvider.jsx';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary.jsx';
import { isNative } from './services/platform';
import { loadToken } from './services/authToken';
import 'leaflet/dist/leaflet.css';
import './styles/colors_and_type.css';
import './styles/global.css';

function render() {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <BrowserRouter>
        <ToastProvider>
          <ToastBridge />
          <AuthProvider>
            <ErrorBoundary>
              <App />
            </ErrorBoundary>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </StrictMode>,
  );
}

// Native app: the stored auth token must be in memory before AuthContext's
// initial /auth/me/ call, or the user would briefly appear logged out.
if (isNative) {
  loadToken().finally(render);
} else {
  render();
}

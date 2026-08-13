import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import { ToastProvider, ToastBridge } from './components/Toast/ToastProvider.jsx';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary.jsx';
import { initSentry } from './services/sentry';
import 'leaflet/dist/leaflet.css';
import './styles/colors_and_type.css';
import './styles/global.css';

// Before render, so errors thrown during the first paint are captured too.
initSentry();

// Renders immediately: the session cookie is sent by the browser on AuthContext's
// initial /auth/me/ call, so there is no stored credential to load first. (The
// native app used to need a token in memory before the first render; that app is
// cancelled and the backend no longer accepts token auth.)
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

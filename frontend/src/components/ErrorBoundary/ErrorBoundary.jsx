import { Component } from 'react';
import { reportError } from '../../services/sentry';

/**
 * Catches render-time errors anywhere below it so a single broken component
 * doesn't blank the whole SPA. Shows a minimal Czech fallback with a reload
 * action. (Error boundaries must be class components in React.)
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) {
      console.error('Uncaught render error:', error, info);
    }
    // React swallows the error once a boundary handles it, so without this
    // Sentry would never see the crashes that actually blank the UI.
    reportError(error, { componentStack: info?.componentStack });
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div style={{ padding: '4rem 1.5rem', textAlign: 'center' }}>
            <h1 style={{ marginBottom: '0.75rem' }}>Něco se pokazilo.</h1>
            <p style={{ marginBottom: '1.5rem' }}>
              Omlouváme se — stránku se nepodařilo zobrazit.
            </p>
            <button type="button" onClick={() => window.location.reload()}>
              Načíst znovu
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}

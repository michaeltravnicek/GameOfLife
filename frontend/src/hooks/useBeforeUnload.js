import { useEffect } from 'react';

/**
 * Warn the user (native browser prompt) before leaving the page while `when`
 * is true — e.g. a form has unsaved changes.
 */
export function useBeforeUnload(when) {
  useEffect(() => {
    if (!when) return undefined;
    const onBeforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [when]);
}

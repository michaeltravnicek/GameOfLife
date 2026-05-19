import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './Toast.css';

const ToastContext = createContext(null);

const DEFAULT_DURATION_MS = 4500;

let nextId = 1;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  /**
   * Show a toast.
   *   type: 'success' | 'error' | 'info' | 'warning'    (default: 'info')
   *   message: string
   *   title?: string (bold first line)
   *   duration?: ms (default 4500). 0 = sticky until dismissed.
   *   action?: { label, onClick }
   * Returns the toast id so the caller can dismiss it manually.
   */
  const show = useCallback((message, opts = {}) => {
    const id = nextId++;
    const toast = {
      id,
      type: opts.type || 'info',
      title: opts.title || null,
      message,
      action: opts.action || null,
    };
    setToasts((prev) => [...prev, toast]);
    const duration = opts.duration ?? DEFAULT_DURATION_MS;
    if (duration > 0) {
      const timer = setTimeout(() => dismiss(id), duration);
      timersRef.current.set(id, timer);
    }
    return id;
  }, [dismiss]);

  // Convenience helpers — same signature as toast.success(message, opts).
  const api = useMemo(() => ({
    show,
    dismiss,
    success: (message, opts = {}) => show(message, { ...opts, type: 'success' }),
    error: (message, opts = {}) => show(message, { ...opts, type: 'error' }),
    info: (message, opts = {}) => show(message, { ...opts, type: 'info' }),
    warning: (message, opts = {}) => show(message, { ...opts, type: 'warning' }),
  }), [show, dismiss]);

  useEffect(() => () => {
    for (const timer of timersRef.current.values()) clearTimeout(timer);
    timersRef.current.clear();
  }, []);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div className="toast-stack" role="region" aria-label="Notifikace" aria-live="polite">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`toast toast-${t.type}`}
              role={t.type === 'error' ? 'alert' : 'status'}
            >
              <div className="toast-icon" aria-hidden="true">
                {t.type === 'success' && '✓'}
                {t.type === 'error' && '!'}
                {t.type === 'warning' && '⚠'}
                {t.type === 'info' && 'ℹ'}
              </div>
              <div className="toast-body">
                {t.title && <div className="toast-title">{t.title}</div>}
                <div className="toast-message">{t.message}</div>
              </div>
              {t.action && (
                <button
                  type="button"
                  className="toast-action"
                  onClick={() => { t.action.onClick(); dismiss(t.id); }}
                >
                  {t.action.label}
                </button>
              )}
              <button
                type="button"
                className="toast-close"
                onClick={() => dismiss(t.id)}
                aria-label="Zavřít"
              >
                ×
              </button>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

/**
 * Module-level proxy that lets non-React code (AuthContext, API interceptors)
 * fire toasts without going through the hook. Wired by ToastBridge below.
 */
let pending = [];
let active = null;

export const toast = {
  show: (...args) => (active ? active.show(...args) : pending.push(['show', args])),
  success: (...args) => (active ? active.success(...args) : pending.push(['success', args])),
  error: (...args) => (active ? active.error(...args) : pending.push(['error', args])),
  info: (...args) => (active ? active.info(...args) : pending.push(['info', args])),
  warning: (...args) => (active ? active.warning(...args) : pending.push(['warning', args])),
  dismiss: (...args) => (active ? active.dismiss(...args) : pending.push(['dismiss', args])),
};

/**
 * Drop this inside <ToastProvider> to make the module-level `toast` proxy work.
 * Bridges the React hook to a plain JS singleton.
 */
export function ToastBridge() {
  const api = useToast();
  useEffect(() => {
    active = api;
    // Flush anything queued before the bridge mounted.
    for (const [method, args] of pending) api[method]?.(...args);
    pending = [];
    return () => { active = null; };
  }, [api]);
  return null;
}

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { reportError } from './errors';
import { toast } from '../components/Toast/ToastProvider';

describe('reportError', () => {
  beforeEach(() => {
    vi.spyOn(toast, 'error').mockImplementation(() => {});
  });

  it('returns a function when called with one argument (fallback only)', () => {
    const handler = reportError('Něco se pokazilo.');
    expect(typeof handler).toBe('function');
  });

  it('uses the server-provided error message when present', () => {
    const handler = reportError('Fallback');
    handler({ response: { data: { error: 'Server řekl ne.' } } });
    expect(toast.error).toHaveBeenCalledWith('Server řekl ne.', { title: 'Chyba' });
  });

  it('falls back to the fallback message when no server error', () => {
    const handler = reportError('Fallback message');
    handler(new Error('boom'));
    expect(toast.error).toHaveBeenCalledWith('Fallback message', { title: 'Chyba' });
  });

  it('uses a generic message when no fallback and no server message', () => {
    const handler = reportError(undefined);
    handler({});
    expect(toast.error).toHaveBeenCalledWith('Něco se nepovedlo.', { title: 'Chyba' });
  });

  it('respects a custom title', () => {
    const handler = reportError('msg', undefined, { title: 'Vlastní titulek' });
    // (passing undefined makes it return a handler, but in this signature the
    // 3rd-arg form is options for the immediate-call shape — verify by direct call)
    reportError('msg', new Error('boom'), { title: 'Vlastní titulek' });
    expect(toast.error).toHaveBeenLastCalledWith('msg', { title: 'Vlastní titulek' });
  });

  it('imperative shape: reportError(fallback, err) reports immediately', () => {
    reportError('Inline fallback', new Error('boom'));
    expect(toast.error).toHaveBeenCalledWith('Inline fallback', { title: 'Chyba' });
  });
});

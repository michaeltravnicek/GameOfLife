import { describe, expect, it, vi, beforeEach } from 'vitest';
import { extractApiError, reportError } from './errors';
import { toast } from '../components/Toast/ToastProvider';

describe('extractApiError', () => {
  it('reads the single-message shape { error }', () => {
    const err = { response: { data: { error: 'Server řekl ne.' } } };
    expect(extractApiError(err, 'Fallback')).toBe('Server řekl ne.');
  });

  it('reads the wrapped field shape { errors: { field: [...] } }', () => {
    const err = { response: { data: { errors: { email: ['Neplatný e-mail.'] } } } };
    expect(extractApiError(err, 'Fallback')).toBe('Neplatný e-mail.');
  });

  it('reads the bare DRF field shape { field: [...] }', () => {
    const err = { response: { data: { rating: ['Toto pole je vyžadováno.'] } } };
    expect(extractApiError(err, 'Fallback')).toBe('Toto pole je vyžadováno.');
  });

  it('reads non_field_errors from DRF validation', () => {
    const err = {
      response: { data: { non_field_errors: ['Zadej šířku i délku, nebo ani jednu.'] } },
    };
    expect(extractApiError(err, 'Fallback')).toBe('Zadej šířku i délku, nebo ani jednu.');
  });

  it('falls back for non-object bodies (e.g. HTML error pages)', () => {
    const err = { response: { data: '<html>500</html>' } };
    expect(extractApiError(err, 'Fallback')).toBe('Fallback');
  });
});

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

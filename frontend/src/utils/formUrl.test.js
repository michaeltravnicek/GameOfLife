import { describe, it, expect } from 'vitest';
import { toFormUrl } from './formUrl';

const RESPONDER = 'https://docs.google.com/forms/d/e/1FAIpQLSabc123/viewform';
// The shape admins actually paste — straight out of the Google Forms editor.
const EDITOR = 'https://docs.google.com/forms/d/1FaxmH4BRn7C/edit?usp=forms_home&ouid=100000000000000000000&ths=true';

describe('toFormUrl', () => {
  it('keeps a responder link as it is', () => {
    expect(toFormUrl(RESPONDER)).toBe(RESPONDER);
  });

  // The whole point: an /edit URL is the author's view, and Google 301s the
  // rewritten /viewform to the public responder form for us.
  it('rewrites an editor link to a viewform link', () => {
    expect(toFormUrl(EDITOR)).toBe('https://docs.google.com/forms/d/1FaxmH4BRn7C/viewform');
  });

  it('never leaks the author account id', () => {
    const open = toFormUrl(EDITOR);
    expect(open).not.toContain('ouid');
    expect(open).not.toContain('100000000000000000000');
  });

  it('drops an #responses fragment', () => {
    expect(toFormUrl('https://docs.google.com/forms/d/1abc/edit#responses'))
      .toBe('https://docs.google.com/forms/d/1abc/viewform');
  });

  it('keeps entry.* params so pre-filled links still work', () => {
    expect(toFormUrl(`${RESPONDER}?entry.123=Michael`)).toContain('entry.123=Michael');
  });

  it('passes forms.gle short links through untouched', () => {
    expect(toFormUrl('https://forms.gle/abc123')).toBe('https://forms.gle/abc123');
  });

  it('rejects non-Google hosts', () => {
    expect(toFormUrl('https://evil.example.com/forms/d/1abc/viewform')).toBeNull();
  });

  it('rejects a Google URL that is not a form', () => {
    expect(toFormUrl('https://docs.google.com/spreadsheets/d/1abc/edit')).toBeNull();
  });

  it('rejects http and other schemes', () => {
    expect(toFormUrl('http://docs.google.com/forms/d/e/1abc/viewform')).toBeNull();
    expect(toFormUrl('javascript:alert(1)')).toBeNull();
  });

  it('handles empty and malformed input without throwing', () => {
    expect(toFormUrl('')).toBeNull();
    expect(toFormUrl(null)).toBeNull();
    expect(toFormUrl(undefined)).toBeNull();
    expect(toFormUrl('not a url at all')).toBeNull();
  });
});

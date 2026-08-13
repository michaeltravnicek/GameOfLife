import { describe, it, expect } from 'vitest';
import { toFormUrls } from './formUrl';

const RESPONDER = 'https://docs.google.com/forms/d/e/1FAIpQLSabc123/viewform';
// The shape admins actually paste — straight out of the Google Forms editor.
const EDITOR = 'https://docs.google.com/forms/d/1FaxmH4BRn7C/edit?usp=forms_home&ouid=100000000000000000000&ths=true';

describe('toFormUrls', () => {
  it('tags a responder link as embedded and keeps a clean open link', () => {
    const { embed, open } = toFormUrls(RESPONDER);
    expect(embed).toBe(`${RESPONDER}?embedded=true`);
    expect(open).toBe(RESPONDER);
  });

  // The whole point: an /edit URL is the author's view, and Google 301s the
  // rewritten /viewform to the public responder form for us.
  it('rewrites an editor link to a viewform link', () => {
    const { embed, open } = toFormUrls(EDITOR);
    expect(open).toBe('https://docs.google.com/forms/d/1FaxmH4BRn7C/viewform');
    expect(embed).toBe('https://docs.google.com/forms/d/1FaxmH4BRn7C/viewform?embedded=true');
  });

  it('never leaks the author account id', () => {
    const { embed, open } = toFormUrls(EDITOR);
    expect(embed).not.toContain('ouid');
    expect(open).not.toContain('100000000000000000000');
  });

  it('drops an #responses fragment', () => {
    const { open } = toFormUrls('https://docs.google.com/forms/d/1abc/edit#responses');
    expect(open).toBe('https://docs.google.com/forms/d/1abc/viewform');
  });

  it('keeps entry.* params so pre-filled links still work', () => {
    const { embed } = toFormUrls(`${RESPONDER}?entry.123=Michael`);
    expect(embed).toContain('entry.123=Michael');
    expect(embed).toContain('embedded=true');
  });

  it('does not double-tag a link that already says embedded', () => {
    const { embed } = toFormUrls(`${RESPONDER}?embedded=true`);
    expect(embed.match(/embedded=true/g)).toHaveLength(1);
  });

  it('passes forms.gle short links through untouched', () => {
    const { embed, open } = toFormUrls('https://forms.gle/abc123');
    expect(embed).toBe('https://forms.gle/abc123');
    expect(open).toBe('https://forms.gle/abc123');
  });

  it('rejects non-Google hosts', () => {
    expect(toFormUrls('https://evil.example.com/forms/d/1abc/viewform')).toBeNull();
  });

  it('rejects a Google URL that is not a form', () => {
    expect(toFormUrls('https://docs.google.com/spreadsheets/d/1abc/edit')).toBeNull();
  });

  it('rejects http and other schemes', () => {
    expect(toFormUrls('http://docs.google.com/forms/d/e/1abc/viewform')).toBeNull();
    expect(toFormUrls('javascript:alert(1)')).toBeNull();
  });

  it('handles empty and malformed input without throwing', () => {
    expect(toFormUrls('')).toBeNull();
    expect(toFormUrls(null)).toBeNull();
    expect(toFormUrls(undefined)).toBeNull();
    expect(toFormUrls('not a url at all')).toBeNull();
  });
});

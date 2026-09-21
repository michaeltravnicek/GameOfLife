import { describe, it, expect } from 'vitest';
import { safeExternalHref } from './safeHref';

describe('safeExternalHref', () => {
  it('passes through the links admins actually paste', () => {
    expect(safeExternalHref('https://chat.whatsapp.com/AbCdEf123')).toBe('https://chat.whatsapp.com/AbCdEf123');
    expect(safeExternalHref('http://example.com/form?x=1&y=2')).toBe('http://example.com/form?x=1&y=2');
    // Stray whitespace from a copy-paste is not a reason to drop the link.
    expect(safeExternalHref('  https://forms.gle/abc  ')).toBe('https://forms.gle/abc');
  });

  it('refuses script and data URLs', () => {
    expect(safeExternalHref('javascript:alert(document.cookie)')).toBeNull();
    // Mixed case and leading whitespace are the classic filter bypasses.
    expect(safeExternalHref('JaVaScRiPt:alert(1)')).toBeNull();
    expect(safeExternalHref(' javascript:alert(1)')).toBeNull();
    expect(safeExternalHref('data:text/html,<script>alert(1)</script>')).toBeNull();
    expect(safeExternalHref('vbscript:msgbox(1)')).toBeNull();
  });

  it('refuses anything that is not an absolute http(s) URL', () => {
    expect(safeExternalHref('chat.whatsapp.com/abc')).toBeNull();
    expect(safeExternalHref('//evil.com')).toBeNull();
    expect(safeExternalHref('/events')).toBeNull();
    expect(safeExternalHref('ftp://files.example.com')).toBeNull();
    expect(safeExternalHref('')).toBeNull();
    expect(safeExternalHref(null)).toBeNull();
    expect(safeExternalHref(undefined)).toBeNull();
    expect(safeExternalHref(42)).toBeNull();
  });
});

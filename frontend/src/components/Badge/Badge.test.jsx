import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Badge from './Badge';

describe('Badge', () => {
  it('defaults to the cream tone on a span', () => {
    render(<Badge>Sport</Badge>);
    const el = screen.getByText('Sport');
    expect(el.tagName).toBe('SPAN');
    expect(el).toHaveClass('gol-badge', 'gol-badge--cream');
  });

  it('applies the requested tone, element and extra class', () => {
    render(<Badge tone="gold" as="li" className="extra" title="t">Brzy</Badge>);
    const el = screen.getByText('Brzy');
    expect(el.tagName).toBe('LI');
    expect(el).toHaveClass('gol-badge--gold', 'extra');
    expect(el).toHaveAttribute('title', 't');
  });
});

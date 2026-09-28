import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Stamp from './Stamp';

describe('Stamp', () => {
  it('defaults to the small gold sticker', () => {
    render(<Stamp>★ Brzy</Stamp>);
    const el = screen.getByText('★ Brzy');
    expect(el).toHaveClass('gol-stamp', 'gol-stamp--gold', 'gol-stamp--sm');
  });

  it('renders the large pink stamp with an arrow that stays out of the label', () => {
    const { container } = render(<Stamp tone="pink" size="lg" arrow>Pokračuje</Stamp>);
    const el = container.querySelector('.gol-stamp');
    expect(el).toHaveClass('gol-stamp--pink', 'gol-stamp--lg');
    expect(container.querySelector('.gol-stamp-arrow')).toHaveAttribute('aria-hidden', 'true');
    expect(el).toHaveTextContent('Pokračuje');
  });

  it('takes a tilt and passes extra props through', () => {
    const { container } = render(<Stamp tilt={4} className="extra" title="t">★ Brzy</Stamp>);
    const el = container.querySelector('.gol-stamp');
    expect(el).toHaveClass('extra');
    expect(el).toHaveAttribute('title', 't');
    expect(el.getAttribute('style')).toContain('--stamp-tilt: 4deg');
  });
});

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import EventCard from './EventCard';

const baseEvent = {
  id: 1,
  slug: 'test-akce',
  name: 'Testovací akce',
  date: '2026-07-01T18:00:00Z',
  place: 'Brno',
  points: 150,
  is_past: false,
};

const wrap = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('EventCard', () => {
  it('uses the event logo from the database when present (dark theme)', () => {
    const logo = 'https://cdn.example.com/event_logos/my-logo.webp';
    wrap(<EventCard event={{ ...baseEvent, logo }} />);
    const badge = screen.getByAltText('Testovací akce');
    expect(badge).toHaveAttribute('src', logo);
  });

  it('falls back to the C50 badge only when no logo is set (dark theme)', () => {
    wrap(<EventCard event={{ ...baseEvent, logo: null }} />);
    const badge = screen.getByAltText('Testovací akce');
    expect(badge).toHaveAttribute('src', '/img/GOL_C50_transparent.webp');
  });

  it('uses the event logo from the database when present (light theme)', () => {
    const logo = 'https://cdn.example.com/event_logos/my-logo.webp';
    const { container } = wrap(<EventCard event={{ ...baseEvent, logo }} theme="light" />);
    const badge = container.querySelector('.evcard-badge');
    expect(badge).toHaveAttribute('src', logo);
  });

  it('falls back to the pink logo only when no logo is set (light theme)', () => {
    const { container } = wrap(<EventCard event={{ ...baseEvent, logo: null }} theme="light" />);
    const badge = container.querySelector('.evcard-badge');
    expect(badge).toHaveAttribute('src', '/img/GOL_main_logo_pink.webp');
  });

  it('links to the event detail page by slug', () => {
    const { container } = wrap(<EventCard event={{ ...baseEvent, logo: null }} />);
    expect(container.querySelector('a')).toHaveAttribute('href', '/events/test-akce');
  });

  it('shows category and status in the footer next to the points (light theme)', () => {
    const event = { ...baseEvent, logo: null, is_past: true, category: { id: 2, name: 'Sport' } };
    const { container } = wrap(<EventCard event={event} theme="light" />);
    const footer = container.querySelector('.evcard-foot-tags');
    expect(footer).toBeTruthy();
    expect(footer).toHaveTextContent('Sport');
    expect(footer).toHaveTextContent('Proběhlo');
    // points pill lives in the same group
    expect(footer.querySelector('.evcard-pts')).toBeTruthy();
  });

  it('omits the category chip when the event has no category', () => {
    const event = { ...baseEvent, logo: null, category: null };
    const { container } = wrap(<EventCard event={event} theme="light" />);
    expect(container.querySelector('.evcard-cat')).toBeNull();
  });
});
